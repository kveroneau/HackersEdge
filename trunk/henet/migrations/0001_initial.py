# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Host'
        db.create_table(u'henet_host', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ip_addr', self.gf('django.db.models.fields.IPAddressField')(max_length=15, db_index=True)),
            ('data', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'henet', ['Host'])


    def backwards(self, orm):
        # Deleting model 'Host'
        db.delete_table(u'henet_host')


    models = {
        u'henet.host': {
            'Meta': {'object_name': 'Host'},
            'data': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'db_index': 'True'})
        }
    }

    complete_apps = ['henet']