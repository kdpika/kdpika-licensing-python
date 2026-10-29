"""Only the new credit-commerce wire contract; signed fixtures, no network."""
import hashlib
import pytest
from kdpika_licensing import LicenseClient, CreditOperationError, NetworkError
from test_credits import CreditTransport, NOW

class CommerceTransport(CreditTransport):
    def __init__(self):
        super().__init__([NOW]);self.balance=0;self.redemptions={};self.drop=False;self.requests=[];self.outer_tamper=False
    def request(self, method, path, body=None, headers=None):
        if not path.startswith('/api/v1/credits/'):
            return super().request(method,path,body,headers)
        self.requests.append((path,body,headers))
        assert headers['X-Installation-ID']==self.last_device
        assert body['fingerprint'] and 'Authorization' in headers
        operation=path.rsplit('/',1)[-1]
        receipt=None;data={'success':True}
        if operation=='redeem':
            code,key=body['code'],body['idempotency_key']
            if code!='KDP100CR':return self.answer({'success':False,'error':{'code':'CREDIT_CODE_UNAVAILABLE'}},422)
            old=self.redemptions.get(key)
            if old:receipt={**old,'replayed':True}
            else:
                self.balance+=100;receipt={'id':'ctx_code_fixture','type':'grant','amount':100,'balance_after':self.balance,'total_allocated_after':100,'idempotency_hash':hashlib.sha256(('code:'+hashlib.sha256(key.encode()).hexdigest()).encode()).hexdigest(),'replayed':False};self.redemptions[key]=receipt
            data.update(added=999 if self.outer_tamper else 100,balance=self.balance,transaction_id=receipt['id'],replayed=receipt['replayed'])
        elif operation=='packs':data['packs']=[{'id':'cpk_fixture','name':'100 credits','units':100,'price':'5.00','currency':'EUR'}]
        elif operation=='checkout':data.update(purchase_id='cpi_fixture',checkout_url='https://store.example.test/?kdpika_credit_checkout='+'a'*64)
        elif operation=='history':data['transactions']=[]
        self.changes.update(credit_balance=self.balance,total_allocated=100,credit_transaction=receipt)
        data['license']=self.signed(self.last_device)
        if self.drop and operation=='redeem':self.drop=False;raise NetworkError()
        return self.answer(data)

@pytest.fixture
def commerce(tmp_path):
    t=CommerceTransport();c=LicenseClient('app_synthetic','sandbox','https://licenses.example.invalid',storage_dir=tmp_path,prefer_keyring=False,transport=t,clock=lambda:NOW)
    assert c.activate('SYNTHETIC-CODE-FIXTURE').valid
    return c,t

def test_redeem_and_replay_signed_current_balance(commerce):
    c,t=commerce;r=c.redeem_credits('KDP100CR','redeem-test-1');assert r['added']==100 and r['balance']==100
    assert c.redeem_credits('KDP100CR','redeem-test-1')['replayed'] and t.balance==100
    assert 'license' not in r

def test_uncertain_redemption_is_not_automatically_retried(commerce):
    c,t=commerce;t.drop=True
    with pytest.raises(NetworkError):c.redeem_credits('KDP100CR','uncertain-code')
    assert len(t.requests)==1 and t.balance==100
    assert c.redeem_credits('KDP100CR','uncertain-code')['replayed'] and t.balance==100

def test_packs_checkout_and_history_use_activation_scope(commerce):
    c,t=commerce;assert c.credit_packs()['packs'][0]['units']==100
    assert c.create_credit_checkout('cpk_fixture')['checkout_url'].startswith('https://store.example.test/')
    assert c.credit_history()['transactions']==[]
    assert all('license_key' not in b and 'email' not in b for _,b,_ in t.requests)

def test_bad_code_and_outer_response_never_fabricate_units(commerce):
    c,t=commerce
    with pytest.raises(CreditOperationError)as e:c.redeem_credits('WRONGCODE','wrong-code-1')
    assert e.value.code=='CREDIT_CODE_UNAVAILABLE' and t.balance==0
    t.outer_tamper=True;assert c.redeem_credits('KDP100CR','outer-fields')['added']==100

def test_async_commerce_wraps_the_same_core(commerce):
    import asyncio
    from kdpika_licensing import AsyncLicenseClient
    c,t=commerce
    async def check():
        adapter=AsyncLicenseClient(c)
        assert (await adapter.redeem_credits('KDP100CR','async-redeem-code'))['added']==100
        assert (await adapter.credit_packs())['packs'][0]['units']==100
        assert (await adapter.create_credit_checkout('cpk_fixture'))['checkout_url'].startswith('https://')
        assert (await adapter.credit_history())['transactions']==[]
    asyncio.run(check())
