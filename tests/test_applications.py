from pathlib import Path
import pytest
from kdpika_licensing import LicenseClient
from kdpika_licensing._applications import application_allowed
from kdpika_licensing._fingerprint import hash_components
import kdpika_licensing.client as client_module
from test_security import MockTransport,NOW

@pytest.mark.parametrize('scope,type,expected', [('both','desktop',True),('both','web',True),('desktop','desktop',True),('desktop','web',False),('web','desktop',False),('web','web',True)])
def test_signed_scope(scope,type,expected):
    assert application_allowed({'application_access':scope,'application_type':type},type) is expected
    assert not application_allowed({'application_access':scope,'application_type':'web' if type=='desktop' else 'desktop'},type)

@pytest.mark.parametrize('scope',[None,True,{},'other'])
def test_malformed_scope(scope):assert not application_allowed({'application_access':scope,'application_type':'desktop'},'desktop')

def test_real_signed_scope_cache_and_headers(tmp_path,monkeypatch):
    monkeypatch.setattr(client_module,'collect_fingerprint',lambda p:hash_components(p,{'baseboard':'fixture-board','cpu':'fixture-cpu'}))
    class Transport(MockTransport):
        seen=[]
        def request(self,method,path,body=None,headers=None):
            self.seen.append(headers or {});return super().request(method,path,body,headers)
    transport=Transport([NOW]);transport.changes.update(application_access='desktop',application_type='desktop')
    with LicenseClient('app_synthetic','SANDBOX','https://example.invalid',storage_dir=tmp_path,prefer_keyring=False,transport=transport,clock=lambda:NOW,application_type='desktop')as desktop:
        assert desktop.activate('SYNTHETIC-KEY').valid
        assert desktop.check().source=='cache'
        assert all(h['X-Application-Type']=='desktop'for h in transport.seen)
        with LicenseClient('app_synthetic','SANDBOX','https://example.invalid',storage_dir=tmp_path,prefer_keyring=False,transport=transport,clock=lambda:NOW,application_type='web')as web:
            assert web.installation_id!=desktop.installation_id
            assert web.activate('SYNTHETIC-KEY').error_code=='APPLICATION_NOT_ALLOWED'
        transport.changes.update(application_access='both',application_type='web')
        assert desktop.validate().error_code=='APPLICATION_NOT_ALLOWED'
