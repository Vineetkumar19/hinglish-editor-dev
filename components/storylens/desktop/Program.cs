using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace StoryLens.Desktop;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        bool verification = Environment.GetEnvironmentVariable("STORYLENS_DESKTOP_VERIFY_DIR") is not null;
        string instanceName = verification ? @"Local\StoryLensDesktop.Verification" : @"Local\StoryLensDesktop";
        using var instance = new Mutex(true, instanceName, out bool firstInstance);
        if (!firstInstance)
        {
            MessageBox.Show("StoryLens is already open. Select it from the Windows taskbar.", "StoryLens");
            return;
        }

        Application.Run(new StoryLensWindow());
    }
}

internal static class Engine
{
    public static readonly Uri Origin = new("http://127.0.0.1:8765/");
    private static readonly HttpClient Client = new(new HttpClientHandler
    {
        UseProxy = false,
        AllowAutoRedirect = false
    }) { Timeout = TimeSpan.FromSeconds(2) };

    public static async Task ConnectAsync(CancellationToken cancellation)
    {
        string root = Path.GetFullPath(Environment.GetEnvironmentVariable("STORYLENS_DESKTOP_ENGINE_ROOT")
            ?? @"D:\Full Drive\remove silence");
        string bridgeFile = Path.Combine(root, "cache", "app", "bridge.json");
        if (await MatchesEngineAsync(bridgeFile, cancellation)) return;

        string python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        if (!File.Exists(python) || !File.Exists(Path.Combine(root, "hinglish_app", "__main__.py")))
            throw new InvalidOperationException("StoryLens could not find its installed editing engine at " + root + ".");

        var start = new ProcessStartInfo(python)
        {
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        foreach (string argument in new[] { "-m", "hinglish_app", "--desktop", "--root", root })
            start.ArgumentList.Add(argument);
        using Process process = Process.Start(start) ?? throw new InvalidOperationException("The editing engine could not start.");

        for (int attempt = 0; attempt < 60; attempt++)
        {
            if (await MatchesEngineAsync(bridgeFile, cancellation)) return;
            if (process.HasExited)
                throw new InvalidOperationException("The local editing engine exited before it was ready (code " + process.ExitCode + ").");
            await Task.Delay(500, cancellation);
        }
        throw new TimeoutException("The local editing engine did not become ready within 30 seconds.");
    }

    private static async Task<bool> MatchesEngineAsync(string bridgeFile, CancellationToken cancellation)
    {
        try
        {
            using HttpResponseMessage response = await Client.GetAsync(new Uri(Origin, "api/health"), cancellation);
            if (response.StatusCode != HttpStatusCode.OK)
                throw new InvalidOperationException("Port 8765 is occupied by a service that does not identify itself as StoryLens.");
            using JsonDocument health = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellation));
            if (!health.RootElement.TryGetProperty("capabilities", out var capabilities) ||
                capabilities.ValueKind != JsonValueKind.Array ||
                !capabilities.EnumerateArray().Any(value => value.GetString() == "browser_native_tools_v1"))
                throw new InvalidOperationException("Port 8765 does not expose the expected StoryLens engine.");

            string installedToken;
            try
            {
                using JsonDocument installed = JsonDocument.Parse(await File.ReadAllTextAsync(bridgeFile, cancellation));
                installedToken = installed.RootElement.GetProperty("token").GetString() ?? "";
            }
            catch (Exception error) when (error is IOException or JsonException or KeyNotFoundException)
            {
                return false;
            }

            // The connection is matched to the installed bridge without sending its saved token.
            using HttpResponseMessage bridgeResponse = await Client.GetAsync(new Uri(Origin, "api/bridge"), cancellation);
            bridgeResponse.EnsureSuccessStatusCode();
            using JsonDocument bridge = JsonDocument.Parse(await bridgeResponse.Content.ReadAsStringAsync(cancellation));
            string actualToken = bridge.RootElement.GetProperty("token").GetString() ?? "";
            if (installedToken.Length == 0 || !CryptographicOperations.FixedTimeEquals(
                Encoding.UTF8.GetBytes(installedToken), Encoding.UTF8.GetBytes(actualToken)))
                throw new InvalidOperationException("The running StoryLens engine belongs to a different workspace.");
            return true;
        }
        catch (HttpRequestException error) when (error.InnerException is SocketException socket &&
            socket.SocketErrorCode == SocketError.ConnectionRefused)
        {
            return false;
        }
    }
}

