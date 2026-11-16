import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from app.common import Message,history_messages
from app.storage import Store

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'db.sqlite')
        self.store=Store(self.path,'ga')
        self.store.add_user('ana')
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def remote(self,lamport=42):
        return Message(id=uuid4(),sender='bob@gb',origin='gb',lamport=lamport,
                       sent_at=datetime.now(timezone.utc),body='hola')
    def test_local_creation_is_atomic_and_idempotent(self):
        key=str(uuid4());m,fresh=self.store.create('ana','hola',key)
        again,new=self.store.create('ana','hola',key)
        self.assertTrue(fresh);self.assertFalse(new);self.assertEqual(m.id,again.id)
        self.assertEqual(self.store.clock(),1);self.assertEqual(len(self.store.pending()),1)
        with self.assertRaises(ValueError):self.store.create('ana','otro',key)
    def test_receive_duplicate_has_no_clock_effect(self):
        m=self.remote();self.assertTrue(self.store.receive(m));self.assertEqual(self.store.clock(),43)
        self.assertFalse(self.store.receive(m));self.assertEqual(self.store.clock(),43)
    def test_restart_keeps_user_history_clock_and_outbox(self):
        self.store.create('ana','persistente',str(uuid4()));self.store.close()
        self.store=Store(self.path,'ga')
        self.assertEqual(self.store.users(),['ana']);self.assertEqual(self.store.clock(),1)
        self.assertEqual(len(self.store.history()),1);self.assertEqual(len(self.store.pending()),1)
    def test_late_low_clock_message_is_not_lost(self):
        self.store.receive(self.remote(100));self.store.receive(self.remote(2))
        self.assertEqual([m['lamport'] for m in self.store.history()],[2,100])
        self.assertEqual(self.store.clock(),102)
    def test_order_uses_origin_when_lamport_equal(self):
        a=self.remote(5);b=self.remote(5);a.origin='gz';b.origin='ga'
        self.store.receive(a);self.store.receive(b)
        self.assertEqual([m['origin'] for m in self.store.history()],['ga','gz'])
    def test_unknown_fields_are_ignored(self):
        data=self.remote().wire();data['future_field']=True
        self.assertNotIn('future_field',Message.model_validate(data).wire())
    def test_pagination_not_silently_ignored(self):
        with self.assertRaises(ValueError):history_messages({'messages':[],'has_more':True})
    def test_group_identity_cannot_change_on_same_db(self):
        with self.assertRaises(ValueError):Store(self.path,'other')

if __name__=='__main__':unittest.main()
