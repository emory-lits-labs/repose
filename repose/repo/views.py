from django.shortcuts import render
from eulfedora.server import Repository
from eulfedora.indexdata.views import index_data

from repose.repo.models import GenericObject

class GenericRepository(Repository):

    def get_object(self, *args, **kwargs):
        if 'type' not in kwargs:
            kwargs['type'] = GenericObject
        return super(GenericRepository, self).get_object(*args, **kwargs)


def stats_index_data(request, id):
    return index_data(request, id, repo=GenericRepository(request=request))
