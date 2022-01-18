# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Topic'
        db.create_table('help_center_topic', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=80)),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=50)),
            ('description', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('help_center', ['Topic'])

        # Adding model 'Guide'
        db.create_table('help_center_guide', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=80)),
            ('slug', self.gf('django.db.models.fields.SlugField')(max_length=50)),
            ('topic', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['help_center.Topic'])),
            ('created_on', self.gf('django.db.models.fields.DateField')(auto_now_add=True, blank=True)),
            ('modified_on', self.gf('django.db.models.fields.DateField')(auto_now=True, blank=True)),
            ('content', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('help_center', ['Guide'])


    def backwards(self, orm):
        # Deleting model 'Topic'
        db.delete_table('help_center_topic')

        # Deleting model 'Guide'
        db.delete_table('help_center_guide')


    models = {
        'help_center.guide': {
            'Meta': {'ordering': "['-modified_on']", 'object_name': 'Guide'},
            'content': ('django.db.models.fields.TextField', [], {}),
            'created_on': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified_on': ('django.db.models.fields.DateField', [], {'auto_now': 'True', 'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'topic': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['help_center.Topic']"})
        },
        'help_center.topic': {
            'Meta': {'object_name': 'Topic'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '80'})
        }
    }

    complete_apps = ['help_center']