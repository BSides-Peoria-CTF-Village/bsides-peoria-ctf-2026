using System.Diagnostics;
using System.Runtime.Serialization;
using System.Text.RegularExpressions;

namespace AeroOps.Workflow;

public sealed class RouteAuditStep
{
    public string? AuditCommand { get; set; }

    public string? ReportName { get; set; }

    public int TimeoutSeconds { get; set; } = 3;

    [OnDeserialized]
    internal void OnDeserialized(StreamingContext context)
    {
        if (string.IsNullOrWhiteSpace(AuditCommand))
        {
            return;
        }

        var reportRoot = Environment.GetEnvironmentVariable("AEROOPS_REPORT_DIR")
            ?? Path.Combine(AppContext.BaseDirectory, "wwwroot", "reports");
        Directory.CreateDirectory(reportRoot);

        var reportName = NormalizeReportName(ReportName);
        var reportPath = Path.Combine(reportRoot, reportName);
        var timeout = Math.Clamp(TimeoutSeconds, 1, 10);

        if (!OperatingSystem.IsLinux())
        {
            File.WriteAllText(reportPath, $"RouteAuditStep only executes on Linux.\ncommand: {AuditCommand}");
            return;
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = "/bin/sh",
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add("-c");
        startInfo.ArgumentList.Add(AuditCommand);

        try
        {
            using var process = Process.Start(startInfo);
            if (process is null)
            {
                File.WriteAllText(reportPath, "Failed to start /bin/sh.");
                return;
            }

            var stdoutTask = process.StandardOutput.ReadToEndAsync();
            var stderrTask = process.StandardError.ReadToEndAsync();

            if (!process.WaitForExit(TimeSpan.FromSeconds(timeout)))
            {
                process.Kill(entireProcessTree: true);
                File.WriteAllText(reportPath, $"Command timed out after {timeout} seconds.\ncommand: {AuditCommand}");
                return;
            }

            File.WriteAllText(reportPath, $"""
            command: {AuditCommand}
            exit code: {process.ExitCode}

            stdout:
            {Trim(stdoutTask.GetAwaiter().GetResult())}

            stderr:
            {Trim(stderrTask.GetAwaiter().GetResult())}
            """);
        }
        catch (Exception ex)
        {
            File.WriteAllText(reportPath, $"""
            command: {AuditCommand}
            error: {ex.Message}
            """);
        }
    }

    private static string NormalizeReportName(string? reportName)
    {
        var value = string.IsNullOrWhiteSpace(reportName) ? "release-audit.txt" : reportName.Trim();
        value = Path.GetFileName(value);
        value = Regex.Replace(value, "[^a-zA-Z0-9_.-]", "-");
        return string.IsNullOrWhiteSpace(value) ? "release-audit.txt" : value;
    }

    private static string Trim(string value)
    {
        const int maxLength = 8192;
        return value.Length <= maxLength ? value : $"{value[..maxLength]}\n... truncated ...";
    }
}
