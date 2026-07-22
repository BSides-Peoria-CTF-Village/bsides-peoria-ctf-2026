namespace AeroDispatchPortal.Operations;

public sealed class FlightReleasePacket
{
    public string? FlightNumber { get; set; }

    public string? TailNumber { get; set; }

    public string? Dispatcher { get; set; }

    public string? Origin { get; set; }

    public string? Destination { get; set; }

    public DateTimeOffset ScheduledDeparture { get; set; }

    public object? RoutingStep { get; set; }

    public FlightLeg[]? Legs { get; set; }
}

public sealed class FlightLeg
{
    public string? From { get; set; }

    public string? To { get; set; }

    public string? Alternates { get; set; }

    public int ReserveMinutes { get; set; }
}
