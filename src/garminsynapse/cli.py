"""Command Line Interface for garminsynapse."""
import click
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("garminsynapse-cli")


@click.group()
def cli():
    """Garmin Synapse - Unified Engine, Database, MCP & Dashboard CLI."""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind server to.")
@click.option("--port", default=6060, help="Port to bind server to.")
def start_server(host, port):
    """Start the FastAPI Web Dashboard & REST API server."""
    import uvicorn
    click.echo(f"🚀 Starting Garmin Synapse Web Dashboard at http://{host}:{port}")
    uvicorn.run("garminsynapse.web.app:app", host=host, port=port, loop="asyncio", http="h11")


@cli.command()
@click.option("--email", prompt=True, help="Garmin Connect account email.")
@click.option("--password", prompt=True, hide_input=True, help="Garmin Connect account password.")
def login(email, password):
    """Interactively authenticate with Garmin Connect, prompting for an MFA code if required."""
    from garminsynapse.auth.manager import DualAuthManager

    def _prompt_mfa():
        return click.prompt("Enter the MFA code sent to your device")

    auth_mgr = DualAuthManager()
    try:
        auth_mgr.login(email, password, prompt_mfa=_prompt_mfa)
        click.echo("✅ Login successful! Tokens & credentials saved for future syncs.")
    except Exception as e:
        click.echo(f"❌ Login failed: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--days", default=30, help="Days of data to extract.")
def sync(days):
    """Sync health and activity data from Garmin Connect."""
    from garminsynapse.etl.extractor import GarminExtractor
    click.echo(f"🔄 Syncing last {days} days of Garmin Connect data...")
    extractor = GarminExtractor()
    extractor.extract_all(days=days)
    from garminsynapse.etl.processor import GarminProcessor
    GarminProcessor().process_ingest_directory()
    click.echo("✅ Sync complete!")


@cli.command()
def mcp():
    """Run the native Python MCP server (STDIO transport)."""
    from garminsynapse.mcp.server import run_server
    click.echo("🤖 Starting Garmin Synapse MCP Server...", err=True)
    run_server()


@cli.command()
@click.option("--days-keep-raw", default=30, help="Days of 1-second raw metrics to keep.")
def downsample(days_keep_raw):
    """Downsample raw 1-second activity time-series metrics."""
    from garminsynapse.db.manager import DatabaseManager
    db = DatabaseManager()
    count = db.downsample(days_keep_raw=days_keep_raw)
    click.echo(f"🧹 Downsampled {count} raw time-series metric rows older than {days_keep_raw} days.")


@cli.command()
@click.option("--days-keep", default=365, help="Days of activities to retain.")
def prune(days_keep):
    """Prune historical records to bound disk usage."""
    from garminsynapse.db.manager import DatabaseManager
    db = DatabaseManager()
    count = db.prune(days_keep=days_keep)
    click.echo(f"✂️ Pruned {count} activity records older than {days_keep} days.")


@cli.command()
@click.argument("activity_id", type=int)
@click.option("--output", "-o", default=None, help="Output directory or file path for the exported file.")
@click.option("--format", "-f", "export_format", default="gpx", type=click.Choice(["gpx"], case_sensitive=False), help="Export format (default: gpx).")
def export(activity_id, output, export_format):
    """Export workout activity to a GPS exchange file (GPX)."""
    import re
    from pathlib import Path
    from garminsynapse.core.api import GarminAPI
    from garminsynapse.db.manager import DatabaseManager
    from garminsynapse.db.schema import Activity

    click.echo(f"📥 Exporting activity {activity_id} ({export_format.upper()})...")
    api = GarminAPI()
    gpx_bytes = api.download_activity_gpx(activity_id)

    if not gpx_bytes:
        click.echo(f"⚠️ Activity {activity_id} does not contain GPS track data or export failed.", err=True)
        raise SystemExit(1)

    act_name = "activity"
    try:
        db = DatabaseManager()
        session = db.get_session()
        try:
            act = session.query(Activity).filter_by(activity_id=activity_id).first()
            if act and act.activity_name:
                clean_name = re.sub(r"[^\w\-_]", "_", act.activity_name).strip("_")
                if clean_name:
                    act_name = clean_name
        finally:
            session.close()
    except Exception:
        pass

    filename = f"{act_name}_{activity_id}.{export_format.lower()}"
    if output:
        out_path = Path(output)
        if out_path.is_dir() or output.endswith("/") or output.endswith("\\") or not out_path.suffix:
            out_path.mkdir(parents=True, exist_ok=True)
            target_file = out_path / filename
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            target_file = out_path
    else:
        target_file = Path.cwd() / filename

    target_file.write_bytes(gpx_bytes)
    size_kb = len(gpx_bytes) / 1024
    click.echo(f"✅ Exported activity {activity_id} to {target_file} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    cli()
