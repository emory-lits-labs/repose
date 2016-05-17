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
from repose.repo.views import stats_index_data, site_index

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^indexdata/$', indexdata_views.index_config, name='index-config'),
    url(r'^indexdata/(?P<id>[^/]+)/$', stats_index_data, name='index-data'),
    url(r'^$', site_index, name='site-index'),
]
