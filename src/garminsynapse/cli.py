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


@cli.group()
def activity():
    """Manage individual activities: reclassify type, detect/fix outliers."""
    pass


@activity.command("set-type")
@click.argument("activity_id", type=int)
@click.argument("type_key")
def activity_set_type(activity_id, type_key):
    """Reclassify ACTIVITY_ID to activity type TYPE_KEY (e.g. 'hiking', 'running')."""
    from garminsynapse.core.api import GarminAPI
    api = GarminAPI()
    try:
        api.change_activity_type(activity_id, type_key)
        click.echo(f"✅ Activity {activity_id} reclassified to '{type_key}'.")
    except Exception as e:
        click.echo(f"❌ Failed to change activity type: {e}", err=True)
        raise SystemExit(1)


def _print_findings(findings):
    if not findings:
        click.echo("✅ No outliers detected.")
        return
    click.echo(f"⚠️  Found {len(findings)} outlier(s):")
    for f in findings:
        click.echo(f"  - [{f['detector']}] index={f['index']} field={f['field']}: {f['reason']}")


@activity.command("preview-corrections")
@click.argument("activity_id", type=int)
def activity_preview_corrections(activity_id):
    """Preview detected outliers for ACTIVITY_ID without changing anything."""
    from garminsynapse.core.api import GarminAPI
    from garminsynapse.core import activity_corrections

    api = GarminAPI()
    result = activity_corrections.preview_corrections(api, activity_id)
    click.echo(f"Activity {activity_id} ({result['sport']}, {result['record_count']} records):")
    _print_findings(result["findings"])


@activity.command("fix")
@click.argument("activity_id", type=int)
@click.option("--dry-run", is_flag=True, help="Preview only; never delete/re-upload.")
def activity_fix(activity_id, dry_run):
    """Detect and correct outliers in ACTIVITY_ID, then delete+re-upload the
    corrected activity to Garmin Connect.

    This is destructive: the corrected activity receives a NEW activity ID,
    and any kudos/comments on the original are lost. A backup of the
    original FIT file is always saved locally first. Requires interactive
    confirmation unless --dry-run is passed.
    """
    from garminsynapse.core.api import GarminAPI
    from garminsynapse.core import activity_corrections

    api = GarminAPI()
    preview = activity_corrections.preview_corrections(api, activity_id)
    click.echo(f"Activity {activity_id} ({preview['sport']}, {preview['record_count']} records):")
    _print_findings(preview["findings"])

    if not preview["findings"]:
        return
    if dry_run:
        click.echo("(dry run: no changes applied)")
        return

    click.echo(
        "\n⚠️  Applying this fix will DELETE the original activity and upload a "
        "corrected replacement (new activity ID; kudos/comments will be lost). "
        "The original FIT file will be backed up locally first."
    )
    if not click.confirm("Proceed?", default=False):
        click.echo("Aborted; no changes made.")
        return

    result = activity_corrections.apply_corrections(api, activity_id, confirm=True)
    if not result["applied"]:
        click.echo(f"No changes applied: {result.get('reason')}")
        return
    click.echo(f"✅ Corrected activity uploaded. Original backed up to {result['backup_path']}")
    click.echo(result["encode_report"]["summary"])


if __name__ == "__main__":
    cli()
