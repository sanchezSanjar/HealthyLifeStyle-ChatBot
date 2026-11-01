// HealthyCoach.exe: starts app.py with the project's .venv (pythonw, no console window).
// Build: launcher\build.bat
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("HealthyCoach")]
[assembly: System.Reflection.AssemblyProduct("HealthyLifeStyle ChatBot")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]

static class HealthyCoachLauncher
{
    [STAThread]
    static int Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string pythonw = Path.Combine(dir, @".venv\Scripts\pythonw.exe");
        string app = Path.Combine(dir, "app.py");
        string log = Path.Combine(dir, "healthycoach.log");

        if (!File.Exists(app))
            return Warn("app.py was not found. Keep HealthyCoach.exe inside the HealthyLifeStyle-ChatBot folder " +
                        "(use a shortcut to start it from the Desktop).");
        if (!File.Exists(pythonw) || !File.Exists(Path.Combine(dir, @"models\base\model.safetensors")))
            return Warn("HealthyCoach is not set up yet.\n\nDouble-click INSTALL_WINDOWS.bat (needs internet once), " +
                        "then open HealthyCoach.exe again.");

        Process process;
        try
        {
            process = Process.Start(new ProcessStartInfo(pythonw, "\"" + app + "\"")
            {
                WorkingDirectory = dir,
                UseShellExecute = false,
            });
        }
        catch (Exception ex)
        {
            return Warn("Could not start Python: " + ex.Message);
        }

        if (process.WaitForExit(6000) && process.ExitCode != 0 && File.Exists(log))
        {
            string[] lines;
            using (var stream = new FileStream(log, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            using (var reader = new StreamReader(stream))
                lines = reader.ReadToEnd().Split('\n');
            string tail = string.Join("\n", lines.Skip(Math.Max(0, lines.Length - 12)));
            if (tail.Trim().Length > 0)
                return Warn("HealthyCoach closed unexpectedly:\n\n" + tail + "\n\nLog: " + log);
        }
        return 0;
    }

    static int Warn(string message)
    {
        MessageBox.Show(message, "HealthyCoach", MessageBoxButtons.OK, MessageBoxIcon.Information);
        return 1;
    }
}
