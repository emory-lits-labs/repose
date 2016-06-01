"""repose URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from eulfedora.indexdata import urls as indexdata_urls
from eulfedora.indexdata import views as indexdata_views
from repose.repo import views as repo_views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^indexdata/$', indexdata_views.index_config, name='index-config'),
    url(r'^indexdata/(?P<id>[^/]+)/$', repo_views.stats_index_data, name='index-data'),
    url(r'^$', repo_views.site_index, name='site-index'),
    # todo: figure out how to organize views better
    url(r'^ds-err/$', repo_views.negative_size, name='negative-size'),
    url(r'^charts/sizes/$', repo_views.size_range, name='size-range'),
    url(r'^charts/sizes.json$', repo_views.size_range_json, name='size-range-json'),
    # would it make sense to organize by types of chart?
    url(r'^charts/treemap/collection/$', repo_views.treemap,
        {'mode': 'collection'}, name='collection-treemap'),
    url(r'^charts/treemap/collection.json$', repo_views.collection_treemap_json,
        name='collection-treemap-json'),
    url(r'^charts/treemap/mimetype/$', repo_views.treemap,
        {'mode': 'mimetype'}, name='mimetype-treemap'),
    url(r'^charts/treemap/mimetype.json$', repo_views.mimetype_treemap_json,
        name='mimetype-treemap-json'),
    url(r'^charts/treemap/mimetype-size/$', repo_views.treemap,
        {'mode': 'mimetype-size'}, name='mimetype-size-treemap'),
    url(r'^charts/treemap/mimetype-size.json$', repo_views.mimetype_size_treemap_json,
        name='mimetype-size-treemap-json'),
]
