# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'UserProfile'
        db.create_table(u'accounts_userprofile', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['auth.User'], unique=True)),
            ('game_access', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('character_limit', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=3)),
        ))
        db.send_create_signal(u'accounts', ['UserProfile'])

        # Adding model 'Character'
        db.create_table(u'accounts_character', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('username', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('ip_addr', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('mailhost', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('bank', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('created_on', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'accounts', ['Character'])

        # Adding model 'HostPool'
        db.create_table(u'accounts_hostpool', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('pool_name', self.gf('django.db.models.fields.CharField')(max_length=60)),
            ('network', self.gf('django.db.models.fields.IPAddressField')(max_length=15, db_index=True)),
            ('counter', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=10)),
            ('mailhost', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('dns', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('bank', self.gf('django.db.models.fields.IPAddressField')(max_length=15)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'accounts', ['HostPool'])


    def backwards(self, orm):
        # Deleting model 'UserProfile'
        db.delete_table(u'accounts_userprofile')

        # Deleting model 'Character'
        db.delete_table(u'accounts_character')

        # Deleting model 'HostPool'
        db.delete_table(u'accounts_hostpool')


    models = {
        u'accounts.character': {
            'Meta': {'object_name': 'Character'},
            'bank': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'created_on': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addr': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'mailhost': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'accounts.hostpool': {
            'Meta': {'object_name': 'HostPool'},
            'bank': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'counter': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '10'}),
            'dns': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'mailhost': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'network': ('django.db.models.fields.IPAddressField', [], {'max_length': '15', 'db_index': 'True'}),
            'pool_name': ('django.db.models.fields.CharField', [], {'max_length': '60'})
        },
        u'accounts.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'character_limit': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '3'}),
            'game_access': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.User']", 'unique': 'True'})
        },
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        }
    }

    complete_apps = ['accounts']