FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /workspace

COPY src/AeroOps.Workflow/AeroOps.Workflow.csproj src/AeroOps.Workflow/
COPY src/AeroDispatchPortal/AeroDispatchPortal.csproj src/AeroDispatchPortal/
RUN dotnet restore src/AeroDispatchPortal/AeroDispatchPortal.csproj

COPY src/ src/
RUN dotnet publish src/AeroDispatchPortal/AeroDispatchPortal.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system ctf \
    && useradd --system --gid ctf --home /app ctf \
    && mkdir -p /app/wwwroot/reports \
    && chown -R ctf:ctf /app

COPY --from=build /app/publish/ ./
COPY flag.txt /flag.txt

ENV ASPNETCORE_URLS=http://0.0.0.0:8080
ENV AEROOPS_REPORT_DIR=/app/wwwroot/reports

RUN chmod 0444 /flag.txt && chown -R ctf:ctf /app

USER ctf
EXPOSE 8080

ENTRYPOINT ["dotnet", "AeroDispatchPortal.dll"]
