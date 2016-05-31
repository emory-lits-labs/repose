from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.template.defaultfilters import filesizeformat
from eulfedora.server import Repository
from eulfedora.indexdata.views import index_data
import scorched
from scorched.strings import WildcardString

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
        "content_model", "collection"]).paginate(rows=0)

    result = facet_query.execute()
    facets = result.facet_counts.facet_fields

    # get collection hierarchy
    response = solr.query(
        solr.Q(content_model='info:fedora/emory-control:Collection-1.0') |
        solr.Q(content_model='info:fedora/emory-control:Collection-1.1'),
        collection__any=True) \
       .field_limit(['pid', 'collection']) \
       .sort_by('pid') \
       .cursor(rows=100)

    collections = {}
    for doc in response:
        # print doc
        collections[doc['pid']] = doc['collection'][0]

    # TODO: combine collection hierarchy with collection facet data
    # maybe use to build something to use with django regroup?
    # https://docs.djangoproject.com/en/1.9/ref/templates/builtins/#regroup

    # get stats on various sizes
    stats_query = solr.query().stats(['object_size', 'xml_size', 'binary_size',
                                      'master_size', 'access_size',
                                      'binary_count'],
                                     facet=['mimetype', 'state']) \
                              .paginate(rows=0).execute()

    # stats + facet pivots = requires solr 5?
    # stats_query = solr.query().stats(['{!tag=piv1 min=true max=true sum=true}object_size']) \
    #                           .pivot_by('{!stats=piv1}content_model,isMemberOfCollection') \
    #                           .paginate(rows=0).execute()

    # if supported, stats should be included under here somewhere
    # print stats_query.facet_counts.facet_pivot

    return render(request, 'repo/index.html', context={
        'total': result.result.numFound,
        'facets': facets,
        'fedora': settings.FEDORA_ROOT,
        'stats': stats_query.stats.stats_fields
        })


def negative_size(request):
    # query solr to find any objects with negative or zero size datastream
    # so they can be fixed
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    # filter on objects with at least one binary datastream
    # look for datastream size 0 or smaller
    # NOTE: wildcard doesn't return expected results;
    # using arbitrary large negative number as lower range end instead
    # response = solr.query(binary_size__range=(WildcardString('*'), 0)) \
    response = solr.query(binary_size__range=(-10000, 0)) \
                   .filter(binary_count__gt=0) \
                   .field_limit(['pid', 'binary_size', 'master_size',
                                 'access_size', 'binary_count']) \
                   .sort_by('pid') \
                   .paginate(rows=100).execute()

    return render(request, 'repo/ds_size_err.html', context={
        'total': response.result.numFound,
        'results': response.result.docs
    })


def size_range_json(request):
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    # use stats query to determine max size
    stats_query = solr.query().stats('master_size') \
                              .paginate(rows=0).execute()
    max_binary_size = int(stats_query.stats.stats_fields['master_size']['max'])

    size_query = response = solr.query() \
                   .facet_range(fields='master_size', start=0,
                                gap=1024*1024*1024,  # gb
                                end=max_binary_size) \
                   .paginate(rows=0)

    data = {'series': []}
    for label, cmodel in GenericObject.cmodels.iteritems():
        response = size_query.filter(content_model=cmodel).execute()
        counts = response.facet_counts.facet_ranges['master_size']['counts']
        # all have the same ranges, so generate categories from whichever is first
        if 'categories' not in data:
            data['categories'] = ['> %s' % filesizeformat(size) for size, count
                                  in counts]

        data['series'].append({
            'name': label,
            'data': [count for size, count in counts]
        })

    return JsonResponse(data)


def size_range(request):
    return render(request, 'repo/size_chart.html')
