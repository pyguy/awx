# Copyright (c) 2017 Ansible, Inc.
# All Rights Reserved.

from uuid import uuid4

from django.conf import LazySettings
from django.core.cache.backends.locmem import LocMemCache
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _
from rest_framework.fields import empty
import pytest

from awx.conf import fields
from awx.conf.settings import SettingsWrapper
from awx.conf.registry import SettingsRegistry


@pytest.fixture()
def reg(request):
    cache = LocMemCache(str(uuid4()), {})  # make a new random cache each time
    settings = LazySettings()
    registry = SettingsRegistry(settings)
    defaults = request.node.get_marker('defaults')
    if defaults:
        settings.configure(**defaults.kwargs)
    settings._wrapped = SettingsWrapper(settings._wrapped,
                                        cache,
                                        registry)
    return registry


def test_simple_setting_registration(reg):
    assert reg.get_registered_settings() == []
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
    )
    assert reg.get_registered_settings() == ['AWX_SOME_SETTING_ENABLED']


def test_simple_setting_unregistration(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
    )
    assert reg.get_registered_settings() == ['AWX_SOME_SETTING_ENABLED']

    reg.unregister('AWX_SOME_SETTING_ENABLED')
    assert reg.get_registered_settings() == []


def test_duplicate_setting_registration(reg):
    "ensure that settings cannot be registered twice."
    with pytest.raises(ImproperlyConfigured):
        for i in range(2):
            reg.register(
                'AWX_SOME_SETTING_ENABLED',
                field_class=fields.BooleanField,
                category=_('System'),
                category_slug='system',
            )


def test_field_class_required_for_registration(reg):
    "settings must specify a field class to register"
    with pytest.raises(ImproperlyConfigured):
        reg.register('AWX_SOME_SETTING_ENABLED')


def test_get_registered_settings_by_slug(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
    )
    assert reg.get_registered_settings(category_slug='system') == [
        'AWX_SOME_SETTING_ENABLED'
    ]
    assert reg.get_registered_settings(category_slug='other') == []


def test_get_registered_read_only_settings(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system'
    )
    reg.register(
        'AWX_SOME_READ_ONLY',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
        read_only=True
    )
    assert reg.get_registered_settings(read_only=True) ==[
        'AWX_SOME_READ_ONLY'
    ]
    assert reg.get_registered_settings(read_only=False) == [
        'AWX_SOME_SETTING_ENABLED'
    ]
    assert reg.get_registered_settings() == [
        'AWX_SOME_SETTING_ENABLED',
        'AWX_SOME_READ_ONLY'
    ]


def test_get_registered_settings_with_required_features(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
        feature_required='superpowers',
    )
    assert reg.get_registered_settings(features_enabled=[]) == []
    assert reg.get_registered_settings(features_enabled=['superpowers']) == [
        'AWX_SOME_SETTING_ENABLED'
    ]


def test_get_dependent_settings(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system'
    )
    reg.register(
        'AWX_SOME_DEPENDENT_SETTING',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
        depends_on=['AWX_SOME_SETTING_ENABLED']
    )
    assert reg.get_dependent_settings('AWX_SOME_SETTING_ENABLED') == set([
        'AWX_SOME_DEPENDENT_SETTING'
    ])


def test_get_registered_categories(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system'
    )
    reg.register(
        'AWX_SOME_OTHER_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('OtherSystem'),
        category_slug='other-system'
    )
    assert reg.get_registered_categories() == {
        'all': _('All'),
        'changed': _('Changed'),
        'system': _('System'),
        'other-system': _('OtherSystem'),
    }


def test_get_registered_categories_with_required_features(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('System'),
        category_slug='system',
        feature_required='superpowers'
    )
    reg.register(
        'AWX_SOME_OTHER_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category=_('OtherSystem'),
        category_slug='other-system',
        feature_required='sortapowers'
    )
    assert reg.get_registered_categories(features_enabled=[]) == {
        'all': _('All'),
        'changed': _('Changed'),
    }
    assert reg.get_registered_categories(features_enabled=['superpowers']) == {
        'all': _('All'),
        'changed': _('Changed'),
        'system': _('System'),
    }
    assert reg.get_registered_categories(features_enabled=['sortapowers']) == {
        'all': _('All'),
        'changed': _('Changed'),
        'other-system': _('OtherSystem'),
    }
    assert reg.get_registered_categories(
        features_enabled=['superpowers', 'sortapowers']
    ) == {
        'all': _('All'),
        'changed': _('Changed'),
        'system': _('System'),
        'other-system': _('OtherSystem'),
    }


def test_is_setting_encrypted(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.CharField,
        category=_('System'),
        category_slug='system'
    )
    reg.register(
        'AWX_SOME_ENCRYPTED_SETTING',
        field_class=fields.CharField,
        category=_('System'),
        category_slug='system',
        encrypted=True
    )
    assert reg.is_setting_encrypted('AWX_SOME_SETTING_ENABLED') is False
    assert reg.is_setting_encrypted('AWX_SOME_ENCRYPTED_SETTING') is True


def test_simple_field(reg):
    reg.register(
        'AWX_SOME_SETTING',
        field_class=fields.CharField,
        category=_('System'),
        category_slug='system',
        placeholder='Example Value',
        feature_required='superpowers'
    )

    field = reg.get_setting_field('AWX_SOME_SETTING')
    assert isinstance(field, fields.CharField)
    assert field.category == _('System')
    assert field.category_slug == 'system'
    assert field.default is empty
    assert field.placeholder == 'Example Value'
    assert field.feature_required == 'superpowers'


def test_field_with_custom_attribute(reg):
    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category_slug='system',
    )

    field = reg.get_setting_field('AWX_SOME_SETTING_ENABLED',
                                  category_slug='other-system')
    assert field.category_slug == 'other-system'


def test_field_with_custom_mixin(reg):
    class GreatMixin(object):

        def is_great(self):
            return True

    reg.register(
        'AWX_SOME_SETTING_ENABLED',
        field_class=fields.BooleanField,
        category_slug='system',
    )

    field = reg.get_setting_field('AWX_SOME_SETTING_ENABLED',
                                  mixin_class=GreatMixin)
    assert isinstance(field, fields.BooleanField)
    assert isinstance(field, GreatMixin)
    assert field.is_great() is True


@pytest.mark.defaults(AWX_SOME_SETTING='DEFAULT')
def test_default_value_from_settings(reg):
    reg.register(
        'AWX_SOME_SETTING',
        field_class=fields.CharField,
        category=_('System'),
        category_slug='system',
    )

    field = reg.get_setting_field('AWX_SOME_SETTING')
    assert field.default == 'DEFAULT'


@pytest.mark.defaults(AWX_SOME_SETTING='DEFAULT')
def test_default_value_from_settings_with_custom_representation(reg):
    class LowercaseCharField(fields.CharField):

        def to_representation(self, value):
            return value.lower()

    reg.register(
        'AWX_SOME_SETTING',
        field_class=LowercaseCharField,
        category=_('System'),
        category_slug='system',
    )

    field = reg.get_setting_field('AWX_SOME_SETTING')
    assert field.default == 'default'
