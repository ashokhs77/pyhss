from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database as database_module
from database import APN, Base, Database, SERVING_APN, SUBSCRIBER


class MemoryLog:
    def __init__(self):
        self.messages = []

    def log(self, **kwargs):
        self.messages.append(kwargs)


def rows_for(engine, subscriber_id, apn_id):
    session = sessionmaker(bind=engine)()
    try:
        return (
            session.query(SERVING_APN)
            .filter_by(subscriber_id=subscriber_id, apn=apn_id)
            .order_by(SERVING_APN.serving_apn_id)
            .all()
        )
    finally:
        session.close()


def test_serving_apn_atomic_lifecycle():
    database_module.config['database']['db_type'] = 'sqlite'
    database_module.config.setdefault('geored', {})['sync_actions'] = []

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        APN(apn_id=2, apn='ims', apn_ambr_dl=1000000, apn_ambr_ul=1000000),
        SUBSCRIBER(
            subscriber_id=1,
            imsi='001019876540096',
            auc_id=1,
            default_apn=2,
            apn_list='2'
        ),
        SUBSCRIBER(
            subscriber_id=2,
            imsi='001019876540104',
            auc_id=2,
            default_apn=2,
            apn_list='2'
        ),
    ])
    session.commit()
    session.add(SERVING_APN(
        subscriber_id=2,
        apn=2,
        pcrf_session_id='other-session',
        serving_pgw='smf.example',
        subscriber_routing=''
    ))
    session.commit()
    session.close()

    database = Database.__new__(Database)
    database.engine = engine
    database.logTool = MemoryLog()
    database.redisMessaging = None
    database.georedEnabled = False

    webhook_calls = []

    def failing_webhook(object_data, operation):
        webhook_calls.append((operation, object_data))
        raise RuntimeError('injected webhook failure')

    database.handleWebhook = failing_webhook

    database.Update_Serving_APN(
        imsi='001019876540096',
        apn='ims',
        pcrf_session_id='session-1',
        serving_pgw='smf.example',
        subscriber_routing='10.46.0.5',
        propagate=False
    )
    first_rows = rows_for(engine, 1, 2)
    assert len(first_rows) == 1
    assert first_rows[0].pcrf_session_id == 'session-1'
    assert len(rows_for(engine, 2, 2)) == 1

    database.Update_Serving_APN(
        imsi='001019876540096',
        apn='ims',
        pcrf_session_id='session-2',
        serving_pgw='smf.example',
        subscriber_routing='10.46.0.5',
        propagate=False
    )
    updated_rows = rows_for(engine, 1, 2)
    assert len(updated_rows) == 1
    assert updated_rows[0].pcrf_session_id == 'session-2'

    database.Update_Serving_APN(
        imsi='001019876540096',
        apn='ims',
        pcrf_session_id='session-1',
        serving_pgw=None,
        subscriber_routing='',
        propagate=False
    )
    after_stale_delete = rows_for(engine, 1, 2)
    assert len(after_stale_delete) == 1
    assert after_stale_delete[0].pcrf_session_id == 'session-2'

    database.Update_Serving_APN(
        imsi='001019876540096',
        apn='ims',
        pcrf_session_id='session-2',
        serving_pgw=None,
        subscriber_routing='',
        propagate=False
    )
    assert rows_for(engine, 1, 2) == []
    assert len(rows_for(engine, 2, 2)) == 1
    assert any(
        '[SERVING_APN_STATE] action=STALE_DELETE_IGNORED' in
        str(message.get('message', ''))
        for message in database.logTool.messages
    )
    assert webhook_calls
