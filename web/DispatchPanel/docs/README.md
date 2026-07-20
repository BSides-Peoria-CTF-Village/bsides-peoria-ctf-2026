This challenge came from research I did at work around insecure .NET deserialization. I had exploited pickle.load before, but .NET’s serialization ecosystem pulled me in because the bug was similar, but also pretty different.

The solve payload is in docs/payloads, and the chain is pretty simple.

Newtonsoft.Json will honor attacker-supplied type metadata when TypeNameHandling is enabled. In this challenge, TypeNameHandling.Auto is paired with a property typed as object, so Json.NET accepts the supplied $type value, instantiates that class, and populates its properties from the JSON body.

The payload points routingStep at the workflow audit gadget. Once Json.NET finishes creating it, the gadget’s deserialization callback fires automatically. The auditCommand property is passed into the audit runner, which executes it on the Linux container. From there, it is straightforward RCE.