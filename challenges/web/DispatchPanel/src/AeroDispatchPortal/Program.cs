using AeroDispatchPortal.Operations;
using Newtonsoft.Json;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/api/schema", () => Results.Json(new
{
    title = "Flight release coordination",
    note = "Release packets carry a routing step used by downstream operations.",
    sample = new
    {
        flightNumber = "AX-4817",
        tailNumber = "N742AX",
        dispatcher = "morgan.lee",
        origin = "KORD",
        destination = "KDEN",
        scheduledDeparture = "2026-06-08T21:35:00Z",
        routingStep = new
        {
            station = "ORD-OCC",
            priority = "normal",
            lane = "westbound"
        }
    }
}));
// guys wait i should have made it more PIA themed
app.MapGet("/api/releases", () => Results.Json(new
{
    endpoint = "/api/releases",
    method = "POST",
    contentType = "application/json",
    status = "accepting flight release packets"
}));

app.MapPost("/api/releases", async (HttpRequest request) =>
{
    using var reader = new StreamReader(request.Body);
    var body = await reader.ReadToEndAsync();

    if (string.IsNullOrWhiteSpace(body))
    {
        return Results.BadRequest(new { error = "The release packet was empty." });
    }

    var settings = new JsonSerializerSettings
    {
        TypeNameHandling = TypeNameHandling.Auto,
        MetadataPropertyHandling = MetadataPropertyHandling.ReadAhead
    };

    try
    {
        var packet = JsonConvert.DeserializeObject<FlightReleasePacket>(body, settings);

        if (packet is null)
        {
            return Results.BadRequest(new { error = "The release packet could not be parsed." });
        }

        var legCount = packet.Legs?.Length ?? 0;
        var reserveMinutes = packet.Legs?.Sum(leg => leg.ReserveMinutes) ?? 0;

        return Results.Json(new
        {
            accepted = true,
            releaseId = $"REL-{DateTimeOffset.UtcNow:yyyyMMddHHmmss}",
            flightNumber = packet.FlightNumber,
            tailNumber = packet.TailNumber,
            route = $"{packet.Origin}-{packet.Destination}",
            legCount,
            reserveMinutes,
            routingStep = packet.RoutingStep?.GetType().FullName ?? "standard-routing",
            status = "released-to-operations"
        });
    }
    catch (JsonSerializationException ex)
    {
        return Results.BadRequest(new { error = "The release packet failed validation.", detail = ex.Message });
    }
    catch (Exception ex)
    {
        return Results.BadRequest(new { error = "The release service crashed.", detail = ex.Message });
    }
});

app.Run();
