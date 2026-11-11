# Optional NVIDIA Eye Contact access

The editor now has an installed, tested free Eye Contact backend. NVIDIA access
is needed only for the optional Maxine implementation described below. See
[the active free backend](EYE_CONTACT_OPEN_MODELS.md).

The existing C++ compiler, Git, Git LFS, and Visual Studio's bundled CMake are installed. The setup script now keeps SDK files, feature downloads, and temporary archives under `C:\Ai Models\maxine`.

NVIDIA's official SDK Core page requires account access:
https://catalog.ngc.nvidia.com/orgs/nvidia/maxine/resources/ar_sdk_core/-

Signing in and creating a Cloud account do not guarantee SDK entitlement. On 2026-10-18 the signed-in account still showed a disabled Download button and an NVIDIA AI Enterprise subscription requirement. Free Developer Program membership alone has not unlocked this SDK. NVIDIA's Maxine page offers a free 90-day evaluation request; approval and SDK entitlement must be confirmed before installation can continue. Do not purchase a subscription as part of this setup without the account owner's explicit approval.

Official evaluation request:
https://enterpriseproductregistration.nvidia.com/?LicType=EVAL&ProductFamily=NVAIEnterprise

Once access is granted, the account owner handles NVIDIA license acceptance. Download the **Windows x86-64** SDK Core ZIP, not the `woa` (Windows on Arm) or Linux package. Extract it so this file exists:

`C:\Ai Models\maxine\ARSDK\features\install_feature.ps1`

After extraction, the project setup can install the gaze-redirection, facial-landmark, and face-box features for compute capability 120, build `GazeRedirectionApp.exe`, save its paths to `config.eyecontact.local.json`, and test it with real video.

NVIDIA's feature installer requires an NGC API key. Enter it only into the setup's secure local prompt. Do not paste it into chat. The project setup uses the key in its process environment and clears a key it prompted for after the installer finishes.

Setup command from the project folder:

```powershell
pwsh -NoProfile -File tools\eyecontact\setup_eyecontact.ps1 -SdkRoot 'C:\Ai Models\maxine\ARSDK'
```

Official instructions:
https://docs.nvidia.com/maxine/ar/latest/WindowsARSDK/InstalltheARSDK.html

The optional Maxine backend remains unavailable until SDK access, feature installation, build, and a real inference check succeed. The free backend and localhost editor work independently of this entitlement.
