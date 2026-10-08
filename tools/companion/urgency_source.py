"""Read-only aggregate adapter for Susi's existing Urgencias report functions."""
import json,os,pathlib,sys
from datetime import datetime
from zoneinfo import ZoneInfo
SUSI=pathlib.Path(os.getenv('SUSI_PROJECT',str(pathlib.Path.home()/'Documents/New project/Susi-Qwen')))
sys.path.insert(0,str(SUSI))

def count_over_three_hours(rows,parse_duration):
    return sum(1 for row in rows if (duration:=parse_duration(row.tardanza)) is not None and duration>3)

def snapshot():
    from web_panel.reports import _load_private_report_environment,_load_module
    root=_load_private_report_environment();sys.path.insert(0,str(root))
    reporter=_load_module('susi_esp32_urgency_reporter',root/'send_drive_report.py')
    tz=ZoneInfo('America/Monterrey');target=datetime.now(tz).date()
    rows=reporter.load_registry_rows_for_reports()
    summary=reporter.build_urgency_summary_data(rows,target)
    delays=reporter.build_urgency_summary_registry_delay_metrics(rows,target,target)
    result={'day':target.isoformat(),'checked':datetime.now(tz).timestamp(),
            'patients':summary['total'],'admissions':summary['admissions'],
            'delay_nursing':delays['delays_over_three'],
            'doctors':dict(summary['doctors']),'nurses':dict(summary['nurses'])}
    # Each independent source can be unavailable without inventing a zero.
    try:
        altas=reporter.get_latest_altas_rows(sheet_id=reporter.required_env('ALTAS_SHEET_ID'),sheet_name=os.getenv('ALTAS_SHEET_TAB',reporter.DEFAULT_ALTAS_SHEET_NAME),lookback_rows=int(os.getenv('UX_ALTAS_LOOKBACK_ROWS','10000')))
        result['voluntary']=reporter.count_altas_range(altas,target,target)
    except Exception:result['voluntary']=None
    try:
        inter=reporter.get_latest_interconsultas_rows(sheet_id=os.getenv('INTERCONSULTAS_SHEET_ID') or reporter.DEFAULT_INTERCONSULTAS_SHEET_ID,sheet_name=os.getenv('INTERCONSULTAS_SHEET_TAB') or reporter.DEFAULT_INTERCONSULTAS_SHEET_NAME,lookback_rows=int(os.getenv('INTERCONSULTAS_LOOKBACK_ROWS',str(reporter.DEFAULT_INTERCONSULTAS_LOOKBACK_ROWS))))
        result['delay_ic']=count_over_three_hours(reporter.build_interconsultas_tarde_data(inter,target)[0],reporter.parse_duration_hours)
    except Exception:result['delay_ic']=None
    result['checked']=datetime.now(tz).timestamp()
    return result

if __name__=='__main__':
    try:print(json.dumps(snapshot(),ensure_ascii=False))
    except Exception as exc:print(json.dumps({'error':type(exc).__name__}));sys.exit(1)
