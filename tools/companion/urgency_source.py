"""Read-only aggregate adapter for Susi's existing Urgencias report functions."""
import json,os,pathlib,sys,unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
SUSI=pathlib.Path(os.getenv('SUSI_PROJECT',str(pathlib.Path.home()/'Documents/New project/Susi-Qwen')))
sys.path.insert(0,str(SUSI))

def count_registry_voluntary(rows,target,parse_date):
    count=0
    for row in rows:
        if len(row)<15 or parse_date(row[0])!=target or not (str(row[2]).strip() or str(row[5]).strip()):continue
        destination=unicodedata.normalize('NFKD',str(row[14])).encode('ascii','ignore').decode().upper()
        destination=' '.join(destination.split())
        if destination in {'AV','AVDOM','AVQX','AV DOM','AV QX','AV/DOM','AV/QX','ALTA VOLUNTARIA','ALTAS VOLUNTARIAS'}:count+=1
    return count

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
    # Today's live Registry controls AV, using the same admission-date window
    # and encounter grain as the other cards. Never infer malformed Altas dates
    # or query the finalized AR historical workbook for current-day counts.
    result['voluntary']=count_registry_voluntary(rows,target,reporter.parse_sheet_date)
    result['voluntary_source']='Registro de Pacientes'
    try:
        inter=reporter.get_latest_interconsultas_rows(sheet_id=os.getenv('INTERCONSULTAS_SHEET_ID') or reporter.DEFAULT_INTERCONSULTAS_SHEET_ID,sheet_name=os.getenv('INTERCONSULTAS_SHEET_TAB') or reporter.DEFAULT_INTERCONSULTAS_SHEET_NAME,lookback_rows=int(os.getenv('INTERCONSULTAS_LOOKBACK_ROWS',str(reporter.DEFAULT_INTERCONSULTAS_LOOKBACK_ROWS))))
        result['delay_ic']=len(reporter.build_interconsultas_tarde_data(inter,target)[0])
    except Exception:result['delay_ic']=None
    result['checked']=datetime.now(tz).timestamp()
    return result

if __name__=='__main__':
    try:print(json.dumps(snapshot(),ensure_ascii=False))
    except Exception as exc:print(json.dumps({'error':type(exc).__name__}));sys.exit(1)
