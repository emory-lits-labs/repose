from django.conf import settings
from django.shortcuts import render
from eulfedora.server import Repository
from eulfedora.indexdata.views import index_data
import scorched

from repose.repo.models import GenericObject


class GenericRepository(Repository):

    def get_object(self, *args, **kwargs):
        if 'type' not in kwargs:
            kwargs['type'] = GenericObject
        return super(GenericRepository, self).get_object(*args, **kwargs)


def stats_index_data(request, id):
    return index_data(request, id, repo=GenericRepository(request=request))


def site_index(request):
    # basic solr queries to get some numbers
    # - # of objects by type
    # - # of objects grouped by collection
    # - total size of objects (by type? TODO)

    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    facet_query = solr.query().facet_by(fields=[
        "content_model", "isMemberOfCollection",
        "mimetype", "state"]).paginate(rows=0)

    result = facet_query.execute()
    facets = result.facet_counts.facet_fields

    # get collection hierarchy
    response = solr.query(
        solr.Q(content_model='info:fedora/emory-control:Collection-1.0') |
        solr.Q(content_model='info:fedora/emory-control:Collection-1.1'),
        isMemberOfCollection__any=True) \
       .field_limit(['pid', 'isMemberOfCollection']) \
       .sort_by('pid') \
       .cursor(rows=100)

    collections = {}
    for doc in response:
        # print doc
        collections[doc['pid']] = doc['isMemberOfCollection'][0]

    # TODO: combine collection hierarchy with collection facet data
    # maybe use to build something to use with django regroup?
    # https://docs.djangoproject.com/en/1.9/ref/templates/builtins/#regroup

    # get stats on various sizes
    stats_query = solr.query().stats(['object_size', 'xml_size', 'binary_size',
                                      'master_size', 'access_size']) \
                              .paginate(rows=0).execute()

    return render(request, 'repo/index.html', context={
        'total': result.result.numFound,
        'facets': facets,
        'fedora': settings.FEDORA_ROOT,
        'stats': stats_query.stats.stats_fields
        })
