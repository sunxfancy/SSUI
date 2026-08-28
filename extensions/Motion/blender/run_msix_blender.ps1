param(
    [Parameter(Mandatory = $true)]
    [string]$Arguments,

    [string]$AppUserModelId = 'BlenderFoundation.Blender_ppwjx1n5r4v9t!BLENDER',

    [switch]$Wait
)

$ErrorActionPreference = 'Stop'

if (-not ('Ssui.ApplicationActivationManager' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace Ssui
{
    [Flags]
    public enum ActivateOptions
    {
        None = 0,
        DesignMode = 1,
        NoErrorUI = 2,
        NoSplashScreen = 4
    }

    [ComImport]
    [Guid("2e941141-7f97-4756-ba1d-9decde894a3d")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IApplicationActivationManager
    {
        int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            ActivateOptions options,
            out uint processId);

        int ActivateForFile(IntPtr appUserModelId, IntPtr itemArray, IntPtr verb, out uint processId);
        int ActivateForProtocol(IntPtr appUserModelId, IntPtr itemArray, out uint processId);
    }

    [ComImport]
    [Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    class ApplicationActivationManagerClass
    {
    }

    public static class ApplicationActivationManager
    {
        public static uint Activate(string appUserModelId, string arguments)
        {
            var manager = (IApplicationActivationManager)new ApplicationActivationManagerClass();
            uint processId;
            int result = manager.ActivateApplication(
                appUserModelId,
                arguments,
                ActivateOptions.NoErrorUI | ActivateOptions.NoSplashScreen,
                out processId);
            Marshal.ThrowExceptionForHR(result);
            return processId;
        }
    }
}
'@
}

$processId = [Ssui.ApplicationActivationManager]::Activate($AppUserModelId, $Arguments)
Write-Output "Activated $AppUserModelId as process $processId"

if ($Wait) {
    Wait-Process -Id $processId
    Write-Output "Process $processId exited"
}
