from diameter import Diameter


class StubLog:
    def log(self, **kwargs):
        return None


class StubDatabase:
    def __init__(self, fail_first=False):
        self.fail_first = fail_first
        self.subscriber_calls = 0

    def Get_Subscriber(self, subscriber_id=None, imsi=None, **kwargs):
        assert subscriber_id == 104 or imsi == '001019876540104'
        self.subscriber_calls += 1
        if self.fail_first and self.subscriber_calls == 1:
            raise RuntimeError('transient database pressure')
        return {
            'subscriber_id': 104,
            'imsi': '001019876540104',
            'msisdn': '9876540104',
            'enabled': True,
        }

    def Get_IMS_Subscriber(self, imsi=None, msisdn=None, **kwargs):
        assert imsi == '001019876540104' or msisdn == '9876540104'
        return {
            'imsi': '001019876540104',
            'msisdn': '9876540104',
            'msisdn_list': '9876540104,9876541104',
        }


def new_diameter(database):
    diameter = Diameter.__new__(Diameter)
    diameter.database = database
    diameter.logTool = StubLog()
    diameter.redisMessaging = None
    return diameter


def test_rx_identity_resolution():
    serving_apn = {
        'subscriber_id': 104,
        'subscriber_routing': '10.46.0.3',
    }

    diameter = new_diameter(StubDatabase())
    by_msisdn = diameter.resolveRxSubscriberFromServingApn(
        'sip:9876540104@ims.mnc001.mcc001.3gppnetwork.org',
        serving_apn,
    )
    assert by_msisdn['imsi'] == '001019876540104'
    assert by_msisdn['msisdn'] == '9876540104'

    by_imsi = diameter.resolveRxSubscriberFromServingApn(
        '001019876540104@ims.mnc001.mcc001.3gppnetwork.org',
        serving_apn,
    )
    assert by_imsi['subscriberDetails']['subscriber_id'] == 104

    by_alias = diameter.resolveRxSubscriberFromServingApn(
        'tel:9876541104',
        serving_apn,
    )
    assert by_alias['imsi'] == '001019876540104'

    mismatch = diameter.resolveRxSubscriberFromServingApn(
        '9876549999@ims.mnc001.mcc001.3gppnetwork.org',
        serving_apn,
    )
    assert mismatch is None

    retry_database = StubDatabase(fail_first=True)
    retried = new_diameter(retry_database).resolveRxSubscriberFromServingApn(
        '9876540104@ims.mnc001.mcc001.3gppnetwork.org',
        serving_apn,
    )
    assert retried['imsi'] == '001019876540104'
    assert retry_database.subscriber_calls == 2

    fallback_diameter = new_diameter(StubDatabase())
    fallback_msisdn = fallback_diameter.resolveRxSubscriberFromSubscriptionId(
        'sip:9876540104@ims.mnc001.mcc001.3gppnetwork.org'
    )
    assert fallback_msisdn['imsi'] == '001019876540104'

    fallback_tel = fallback_diameter.resolveRxSubscriberFromSubscriptionId(
        'tel:9876540104'
    )
    assert fallback_tel['subscriberDetails']['enabled'] is True

    fallback_imsi = fallback_diameter.resolveRxSubscriberFromSubscriptionId(
        '001019876540104@ims.mnc001.mcc001.3gppnetwork.org'
    )
    assert fallback_imsi['msisdn'] == '9876540104'
