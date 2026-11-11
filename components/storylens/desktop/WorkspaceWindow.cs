using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace StoryLens.Desktop;

internal sealed class StoryLensWindow : Form
{
    private static readonly HashSet<int> LocalToolPorts = [8765, 4310, 43820, 43822, 8879, 8880, 8883, 8894, 8896];
    private static readonly Color Surface = Color.FromArgb(29, 29, 31);
    private static readonly Color Ink = Color.FromArgb(233, 231, 230);
    private readonly CancellationTokenSource lifetime = new();
    private readonly Dictionary<string, Workspace> workspaces = new();
    private readonly Stack<(Workspace Workspace, string? Tool)> history = new();
    private readonly Panel content = new() { Dock = DockStyle.Fill, BackColor = Surface };
    private readonly BackArrow back = new() { Visible = false };
    private readonly ToolTip tooltip = new();
    private readonly Workspace editor;
    private Workspace active;
    private CoreWebView2Environment? environment;
    private bool verification;
    private bool closing;

    public StoryLensWindow()
    {
        Text = "StoryLens";
        if (Environment.ProcessPath is { } executable)
            Icon = Icon.ExtractAssociatedIcon(executable) ?? Icon;
        Width = 1440;
        Height = 920;
        MinimumSize = new Size(760, 540);
        WindowState = FormWindowState.Maximized;
        BackColor = Surface;

        Controls.Add(content);
        editor = AddWorkspace(Engine.Origin);
        active = editor;
        content.Controls.Add(back);
        ShowWorkspace(editor);
        back.Click += async (_, _) => await GoBackAsync();
        content.Resize += (_, _) => PositionBackArrow();
        PositionBackArrow();
        Shown += async (_, _) => await StartAsync();
        FormClosed += (_, _) =>
        {
            closing = true;
            lifetime.Cancel();
            tooltip.Dispose();
        };
    }

    private async Task StartAsync()
    {
        string? directory = Environment.GetEnvironmentVariable("STORYLENS_DESKTOP_VERIFY_DIR");
        verification = directory is not null;
        try
        {
            await LoadWorkspaceAsync(editor);
            if (directory is not null) await VerifyAsync(directory);
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error)
        {
            if (directory is not null)
                File.WriteAllText(Path.Combine(directory, "error.txt"), error.ToString());
        }
        finally
        {
            if (directory is not null && !IsDisposed) Close();
        }
    }

    private Workspace AddWorkspace(Uri address)
    {
        var workspace = new Workspace(address, address == Engine.Origin ? "Editor" : WorkspaceName(address));
        workspace.Retry.Click += async (_, _) => await LoadWorkspaceAsync(workspace);
        workspaces.Add(workspace.Key, workspace);
        content.Controls.Add(workspace.Panel);
        return workspace;
    }

    private void PositionBackArrow()
    {
        int margin = LogicalToDeviceUnits(14);
        int size = LogicalToDeviceUnits(34);
        back.SetBounds(margin, Math.Max(margin, content.ClientSize.Height - size - margin), size, size);
    }

    private void ShowWorkspace(Workspace workspace)
    {
        if (active != workspace)
        {
            active.Panel.Visible = false;
            active = workspace;
        }
        workspace.Panel.Visible = true;
        workspace.Panel.BringToFront();
        UpdateBackArrow();
    }

    private void UpdateBackArrow()
    {
        back.Visible = history.TryPeek(out var previous);
        tooltip.SetToolTip(back, previous.Workspace is null ? "Back" :
            previous.Tool is not null ? "Back to previous tool" : "Back to " + previous.Workspace.Name);
        back.BringToFront();
    }

    private async Task OpenWorkspaceAsync(Uri address)
    {
        if (closing) return;
        Workspace workspace;
        if (IsEditor(address))
        {
            workspace = editor;
        }
        else if (!workspaces.TryGetValue(address.AbsoluteUri, out workspace!))
        {
            workspace = AddWorkspace(address);
        }

        bool changedWorkspace = workspace != active;
        if (changedWorkspace) history.Push((active, null));
        ShowWorkspace(workspace);

        if (workspace.View.CoreWebView2 is null || workspace.Failed)
        {
            workspace.Address = address;
            await LoadWorkspaceAsync(workspace);
        }
        else if (workspace == editor && address.Query.Length != 0)
        {
            var core = editor.View.CoreWebView2;
            string url = JsonSerializer.Serialize(address.AbsoluteUri);
            string handled = await core.ExecuteScriptAsync($"window.storyLensSelectLinkedTool?.({url}) === true");
            if (handled != "true" && core.Source != address.AbsoluteUri)
                core.Navigate(address.AbsoluteUri);
        }
    }

    private async Task GoBackAsync()
    {
        if (!history.TryPop(out var previous)) return;
        Workspace leaving = active;
        ShowWorkspace(previous.Workspace);
        if (previous.Tool is { } tool && active == editor && editor.View.CoreWebView2 is { } core)
            await core.ExecuteScriptAsync($"window.storyLensRestoreTool?.({JsonSerializer.Serialize(tool)})");

        if (leaving != active && leaving != editor && !history.Any(row => row.Workspace == leaving))
        {
            workspaces.Remove(leaving.Key);
            leaving.Panel.Dispose();
        }
    }

    private async Task LoadWorkspaceAsync(Workspace workspace)
    {
        if (workspace.Loading || workspace.Panel.IsDisposed) return;
        workspace.Loading = true;
        workspace.SetStatus("Opening " + workspace.Name + "…");
        try
        {
            if (workspace.Address.Port == Engine.Origin.Port)
                await Engine.ConnectAsync(lifetime.Token);
            if (workspace.Panel.IsDisposed || closing) return;
            if (workspace.View.CoreWebView2 is null)
                await InitializeViewAsync(workspace);
            if (workspace.Panel.IsDisposed || closing) return;
            var core = workspace.View.CoreWebView2 ?? throw new InvalidOperationException("The Windows view did not initialize.");
            core.Navigate(workspace.Address.AbsoluteUri);
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error)
        {
            if (!workspace.Panel.IsDisposed && !closing)
                workspace.SetStatus(error.Message, failed: true);
        }
        finally
        {
            workspace.Loading = false;
        }
    }

    private async Task InitializeViewAsync(Workspace workspace)
    {
        string profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "StoryLens", "WebView2");
        if (verification) profile = Path.Combine(profile, "Verification");
        environment ??= await CoreWebView2Environment.CreateAsync(userDataFolder: profile);
        lifetime.Token.ThrowIfCancellationRequested();
        if (workspace.Panel.IsDisposed) return;
        await workspace.View.EnsureCoreWebView2Async(environment);
        if (workspace.Panel.IsDisposed || closing) return;

        var core = workspace.View.CoreWebView2;
        core.Settings.AreHostObjectsAllowed = false;
        core.Settings.IsWebMessageEnabled = workspace == editor;
        core.Settings.AreDevToolsEnabled = false;
        core.Settings.IsStatusBarEnabled = false;
        if (workspace == editor)
        {
            core.WebMessageReceived += (_, args) =>
            {
                if (active != editor || !TryLocal(args.Source, out var origin) || !IsEditor(origin) ||
                    origin.GetLeftPart(UriPartial.Authority) != Engine.Origin.GetLeftPart(UriPartial.Authority)) return;
                string message;
                try { message = args.TryGetWebMessageAsString(); }
                catch (ArgumentException) { return; }
                if (!message.StartsWith("tool:", StringComparison.Ordinal) || message.Length is < 6 or > 70) return;
                string previousTool = message[5..];
                if (!previousTool.All(char.IsAsciiLetterOrDigit)) return;
                history.Push((editor, previousTool));
                UpdateBackArrow();
            };
            await core.AddScriptToExecuteOnDocumentCreatedAsync("""
                if (window.top === window && location.origin === 'http://127.0.0.1:8765'
                    && (location.pathname === '/' || location.pathname === '/index.html')) {
                  let restoring = false;
                  const toolButton = name => [...document.querySelectorAll('button.mode[data-mode]')]
                    .find(button => button.dataset.mode === name);
                  window.storyLensRestoreTool = name => {
                    const button = toolButton(name);
                    if (!button) return;
                    restoring = true;
                    try { button.click(); } finally { restoring = false; }
                  };
                  window.storyLensSelectLinkedTool = url => {
                    const query = new URL(url).searchParams;
                    const name = query.get('tool');
                    if (!name || !toolButton(name) || [...query.keys()].some(key => key !== 'tool')) return false;
                    window.storyLensRestoreTool(name);
                    return true;
                  };
                  document.addEventListener('click', event => {
                    const button = event.target.closest?.('button.mode[data-mode]');
                    const previous = document.querySelector('button.mode.active')?.dataset.mode;
                    if (!restoring && button && previous && previous !== button.dataset.mode)
                      window.chrome.webview.postMessage('tool:' + previous);
                  }, true);
                }
                """);
        }
        else
        {
            await core.AddScriptToExecuteOnDocumentCreatedAsync("""
                if (window.top === window && location.origin === 'http://127.0.0.1:8765') {
                  document.addEventListener('DOMContentLoaded', () => {
                    const browserNavigation = {
                      '/downloader.html': 'body > header',
                      '/finance.html': 'nav[aria-label="Finance workspace"] > a[href="/"]',
                      '/creator-analytics.html': '.rail > a.back',
                      '/ai-agents.html': 'body > header > a[href="/"]:not(.brand)'
                    }[location.pathname];
                    if (browserNavigation) document.querySelector(browserNavigation)?.remove();
                  }, {once: true});
                }
                """);
        }
        core.NavigationStarting += (_, args) =>
        {
            if (!TryLocal(args.Uri, out var address))
            {
                args.Cancel = true;
                if (args.IsUserInitiated) OpenWebLink(args.Uri);
                return;
            }
            bool toAnotherPage = !args.IsRedirected && IsDocument(address) &&
                (workspace == editor ? !IsEditor(address) : !SameDocument(address, workspace.Address));
            if (toAnotherPage)
            {
                args.Cancel = true;
                BeginInvoke((Action)(async () =>
                {
                    if (workspace == active) await OpenWorkspaceAsync(address);
                }));
                return;
            }
            workspace.Address = address;
        };
        core.FrameNavigationStarting += (sender, args) =>
        {
            if (!TryLocal(args.Uri, out _) && args.Uri != "about:blank") args.Cancel = true;
        };
        core.PermissionRequested += (_, args) =>
        {
            if (!Uri.TryCreate(args.Uri, UriKind.Absolute, out var origin) ||
                origin.GetLeftPart(UriPartial.Authority) != Engine.Origin.GetLeftPart(UriPartial.Authority))
                args.State = CoreWebView2PermissionState.Deny;
        };
        core.NewWindowRequested += (_, args) =>
        {
            args.Handled = true;
            if (TryLocal(args.Uri, out var address))
                BeginInvoke((Action)(async () =>
                {
                    if (workspace == active) await OpenWorkspaceAsync(address);
                }));
            else if (args.IsUserInitiated)
                OpenWebLink(args.Uri);
        };
        core.NavigationCompleted += (_, args) =>
        {
            if (args.IsSuccess && args.HttpStatusCode < 400)
                workspace.ShowContent();
            else if (args.WebErrorStatus != CoreWebView2WebErrorStatus.OperationCanceled)
                workspace.SetStatus(workspace.Name + " couldn’t load.", failed: true);
        };
    }

    private static bool TryLocal(string address, out Uri uri)
    {
        if (Uri.TryCreate(address, UriKind.Absolute, out var parsed) && parsed.Scheme == Uri.UriSchemeHttp &&
            (parsed.Host == "127.0.0.1" || parsed.Host == "localhost") && parsed.UserInfo.Length == 0 &&
            LocalToolPorts.Contains(parsed.Port))
        {
            uri = parsed;
            return true;
        }
        uri = null!;
        return false;
    }

    private static bool IsEditor(Uri address) => address.Port == Engine.Origin.Port &&
        (address.AbsolutePath == "/" || address.AbsolutePath == "/index.html");

    private static bool SameDocument(Uri left, Uri right) =>
        left.GetLeftPart(UriPartial.Query) == right.GetLeftPart(UriPartial.Query);

    private static bool IsDocument(Uri address) => !address.AbsolutePath.StartsWith("/api/", StringComparison.OrdinalIgnoreCase) &&
        (Path.GetExtension(address.AbsolutePath) is "" or ".html" || address.AbsolutePath.EndsWith('/'));

    private static string WorkspaceName(Uri address)
    {
        string? named = address.Port switch
        {
            4310 => "Finance Tracker", 43820 => "Pocket Tracker", 43822 => "Freelancer Finance",
            8879 => "Cricket Desk", 8880 => "Gaming Desk", 8883 => "Editor Handoff",
            8894 => "Reel Recreate", 8896 => "Hook Drafts", _ => null
        };
        if (named is not null) return named;
        string name = Path.GetFileNameWithoutExtension(address.AbsolutePath).Replace('-', ' ').Replace('_', ' ').Trim();
        return name.Length == 0 ? "Local workspace" : char.ToUpperInvariant(name[0]) + name[1..];
    }

    private static void OpenWebLink(string address)
    {
        if (!Uri.TryCreate(address, UriKind.Absolute, out var uri) || uri.Scheme != Uri.UriSchemeHttps ||
            uri.UserInfo.Length != 0) return;
        try { Process.Start(new ProcessStartInfo(uri.AbsoluteUri) { UseShellExecute = true }); }
        catch (System.ComponentModel.Win32Exception)
        {
            MessageBox.Show("Windows could not open this link in the default browser.", "StoryLens");
        }
    }

    private async Task VerifyAsync(string directory)
    {
        await WaitForPageAsync(editor, "!!document.querySelector('[data-mode=clean]')", "Editor did not open.");
        if (editor.Panel.Bounds != content.ClientRectangle || content.Bounds != ClientRectangle || back.Visible)
            throw new InvalidOperationException("The editor does not fill the app window.");
        var editorCore = editor.View.CoreWebView2;
        await editorCore.ExecuteScriptAsync("window.storyLensFlowProof = true; document.querySelector('[data-mode=downloader]').click()");
        await WaitForPageAsync(editor, "!!document.querySelector('iframe[data-tool=downloader]')?.contentDocument?.querySelector('#downloadForm')",
            "The editor tool did not render.");
        await WaitForAsync(() => back.Visible && history.Count == 1, "The in-editor tool did not enter the navigation flow.");

        await editorCore.ExecuteScriptAsync("location.href='/downloader.html'");
        await WaitForAsync(() => active.Name == "Downloader", "The second screen did not open.");
        var downloader = active;
        await WaitForPageAsync(downloader, "!!document.querySelector('#downloadForm')", "The Downloader screen did not render.");
        await downloader.View.CoreWebView2.ExecuteScriptAsync("window.storyLensDownloaderProof = true");
        const string missing = "/__storylens_desktop_missing_page__";
        await downloader.View.CoreWebView2.ExecuteScriptAsync($"location.href={JsonSerializer.Serialize(missing)}");
        await WaitForAsync(() => active.Failed && active.Address.AbsolutePath == missing && back.Visible && history.Count == 3,
            "A failed screen did not keep its place in the navigation flow.");

        using (var image = new Bitmap(back.Width, back.Height))
        {
            back.DrawToBitmap(image, back.ClientRectangle);
            image.Save(Path.Combine(directory, "circular-back-arrow.png"));
        }
        back.PerformClick();
        await WaitForPageAsync(downloader, "window.storyLensDownloaderProof === true", "Back did not restore the Downloader screen.");
        back.PerformClick();
        await WaitForPageAsync(editor, "window.storyLensFlowProof === true && !!document.querySelector('[data-mode=downloader].active')",
            "Back did not restore the editor and its active tool.");
        back.PerformClick();
        await WaitForPageAsync(editor, "!!document.querySelector('[data-mode=clean].active')", "Back did not restore Smart Clean.");
        await WaitForAsync(() => !back.Visible && history.Count == 0, "Back did not finish at the initial screen.");

        const string rejected = "https://example.invalid/";
        var blocked = new TaskCompletionSource<bool>();
        void ObserveBlock(object? sender, CoreWebView2NavigationStartingEventArgs args)
        {
            if (args.Uri == rejected) blocked.TrySetResult(args.Cancel);
        }
        editorCore.NavigationStarting += ObserveBlock;
        editorCore.Navigate(rejected);
        if (!await blocked.Task.WaitAsync(TimeSpan.FromSeconds(5)))
            throw new InvalidOperationException("External navigation was not blocked.");
        editorCore.NavigationStarting -= ObserveBlock;
        File.WriteAllText(Path.Combine(directory, "verified.json"), JsonSerializer.Serialize(new
        {
            fillsWindow = true, circularBack = true, reverseOrder = true, toolStatePreserved = true,
            backedOutOfFailedPage = true, externalNavigationBlocked = true
        }));
    }

    private async Task WaitForPageAsync(Workspace workspace, string expression, string error)
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            if (active == workspace && workspace.View.Visible && workspace.View.CoreWebView2 is { } core &&
                await core.ExecuteScriptAsync(expression) == "true") return;
            await Task.Delay(250, lifetime.Token);
        }
        throw new InvalidOperationException(error);
    }

    private async Task WaitForAsync(Func<bool> ready, string error)
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            if (ready()) return;
            await Task.Delay(250, lifetime.Token);
        }
        throw new InvalidOperationException(error);
    }

    private sealed class Workspace
    {
        public string Name { get; }
        public string Key { get; }
        public Uri Address { get; set; }
        public bool Failed { get; private set; }
        public bool Loading { get; set; }
        public Panel Panel { get; } = new() { Dock = DockStyle.Fill, Visible = false, BackColor = Surface };
        public WebView2 View { get; } = new() { Dock = DockStyle.Fill, Visible = false };
        public Button Retry { get; } = new()
        {
            Text = "Retry", AutoSize = true, Visible = false, Anchor = AnchorStyles.None,
            Margin = new Padding(0, 12, 0, 0), FlatStyle = FlatStyle.Flat, ForeColor = Ink, BackColor = Surface
        };
        private readonly TableLayoutPanel empty = new() { Dock = DockStyle.Fill, RowCount = 4, ColumnCount = 1, BackColor = Surface };
        private readonly Label message = new()
        {
            AutoSize = true, MaximumSize = new Size(600, 0), Anchor = AnchorStyles.None,
            TextAlign = ContentAlignment.MiddleCenter, Font = new Font("Segoe UI", 13), ForeColor = Ink
        };

        public Workspace(Uri address, string name)
        {
            Address = address;
            Key = address.AbsoluteUri;
            Name = name;
            empty.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
            empty.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            empty.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            empty.RowStyles.Add(new RowStyle(SizeType.Percent, 50));
            empty.Controls.Add(message, 0, 1);
            empty.Controls.Add(Retry, 0, 2);
            Panel.Controls.Add(View);
            Panel.Controls.Add(empty);
        }

        public void SetStatus(string text, bool failed = false)
        {
            Failed = failed;
            message.Text = text;
            Retry.Visible = failed;
            View.Visible = false;
            empty.Visible = true;
            empty.BringToFront();
        }

        public void ShowContent()
        {
            Failed = false;
            empty.Visible = false;
            View.Visible = true;
        }
    }

    private sealed class BackArrow : Button
    {
        public BackArrow()
        {
            AccessibleName = "Back";
            Cursor = Cursors.Hand;
            SetStyle(ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            MouseEnter += (_, _) => Invalidate();
            MouseLeave += (_, _) => Invalidate();
        }

        protected override void OnSizeChanged(EventArgs args)
        {
            base.OnSizeChanged(args);
            if (Width == 0 || Height == 0) return;
            using var circle = new GraphicsPath();
            circle.AddEllipse(ClientRectangle);
            Region? old = Region;
            Region = new Region(circle);
            old?.Dispose();
        }

        protected override void OnPaint(PaintEventArgs args)
        {
            var g = args.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using var fill = new SolidBrush(ClientRectangle.Contains(PointToClient(MousePosition))
                ? Color.FromArgb(65, 65, 68) : Color.FromArgb(45, 45, 48));
            using var border = new Pen(Focused ? Color.FromArgb(255, 136, 83) : Color.FromArgb(92, 92, 96));
            using var stroke = new Pen(Ink, Math.Max(1.5f, Width / 19f))
                { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
            var rim = new RectangleF(0.8f, 0.8f, Width - 1.6f, Height - 1.6f);
            g.FillEllipse(fill, rim);
            g.DrawEllipse(border, rim);
            float x = Width / 2f;
            float y = Height / 2f;
            float tip = Width * 0.16f;
            float shoulder = Width * 0.035f;
            g.DrawLines(stroke, [new PointF(x + shoulder, y - tip), new PointF(x - tip, y), new PointF(x + shoulder, y + tip)]);
            g.DrawLine(stroke, x - tip, y, x + tip, y);
        }
    }
}
