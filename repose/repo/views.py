from collections import OrderedDict
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import JsonResponse, HttpResponse
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
            solr.Q(content_model='info:fedora/emory-control:Collection-1.1')) \
       .filter(type='object') \
       .field_limit(['pid', 'collection', 'label', 'id']) \
       .sort_by('id') \
       .cursor(rows=100)

    # gather collection labels & parents
    parents = {}
    labels = {}
    for doc in response:
        labels[doc['pid']] = doc['label']
        if 'collection' in doc:
            parents[doc['pid']] = doc['collection'][0]

    # preliminary work to combine collection hierarchy & labels with facet data
    # django regroup doesn't work for this; construct a dict (ordereddict maybe?)
    # with hierarchy instead
    collections = {}
    for value, count in facets['collection']:
        pid = value.replace('info:fedora/', '')
        parent_collection = parents.get(pid, None)
        collection_info = {
            'pid': value,
            'label': labels[pid],
            'count': count,
            'parent': parent_collection
        }
        if parent_collection is not None:
            if parent_collection not in collections:
                collections[parent_collection] = {'collections': []}
            collections[parent_collection]['collections'].append(collection_info)
        else:
            if parent_collection not in collections:
                collections[pid] = {'collections': []}
            collections[pid].update(collection_info)

    # get stats on various sizes
    stats_query = solr.query() \
                      .filter(type='object') \
                      .stats(['size', 'xml_size', 'binary_size',
                              'master_size', 'access_size',
                              'binary_count'],
                             facet=['mimetype', 'state']) \
                      .paginate(rows=0).execute()

    ds_stats_query = solr.query() \
                        .filter(type='dsversion') \
                        .stats('size', facet=['mimetype', 'control_group']) \
                        .paginate(rows=0).execute()

    print ds_stats_query.stats.stats_fields

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
        'stats': stats_query.stats.stats_fields,
        'ds_stats': ds_stats_query.stats.stats_fields,
        'collections': collections
        })


def check_indexing(request):
    # compare solr index counts to risearch counts as a sanity-check
    # to identify content that is not indexed

    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    facet_query = solr.query().filter(type='object')\
                      .facet_by(fields=["content_model"]).paginate(rows=0)

    result = facet_query.execute()
    total = {'solr': result.result.numFound}
    facets = result.facet_counts.facet_fields

    repo = Repository()
    itql_cmodel_count = '''select $cmodel
count(select $item from <#ri>
where $item <info:fedora/fedora-system:def/model#hasModel> $cmodel)
from <#ri>
where $item <info:fedora/fedora-system:def/model#hasModel> $cmodel
having $k0 <http://mulgara.org/mulgara#occursMoreThan> '0.0'^^<http://www.w3.org/2001/XMLSchema#double> ;'''

    stmts = repo.risearch.find_statements(itql_cmodel_count,
                                          language='itql', type='tuples')

    cmodel_counts = OrderedDict()
    for cmodel, count in facets['content_model']:
        cmodel_counts[cmodel] = {'solr': count}

    for info in stmts:
        cmodel = info['cmodel']
        count = info['k0']
        if cmodel not in cmodel_counts:
            cmodel_counts[cmodel] = {'solr': 0}
        cmodel_counts[cmodel].update({
            'risearch': count,
            'diff': cmodel_counts[cmodel]['solr'] - int(count)
        })

    total['risearch'] = repo.risearch.count_statements(
        '* <fedora-model:hasModel> <info:fedora/fedora-system:FedoraObject-3.0>')
    total['diff'] = total['solr'] - total['risearch']

    return render(request, 'repo/check_indexing.html', context={
        'cmodel_counts': cmodel_counts,
        'total': total
    })


def negative_size(request, mode='display'):
    # query solr to find any objects with negative or zero size datastream
    # so they can be fixed
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    # filter on objects with at least one binary datastream
    # look for datastream size 0 or smaller
    # NOTE: wildcard doesn't return expected results;
    # using arbitrary large negative number as lower range end instead
    # response = solr.query(binary_size__range=(WildcardString('*'), 0)) \
    query = solr.query(binary_size__range=(-10000, 0)) \
                .filter(binary_count__gt=0) \
                .sort_by('pid')

    if mode == 'display':
        response = query.field_limit(['pid', 'binary_size', 'master_size',
                                      'access_size', 'binary_count']) \
                        .paginate(rows=100).execute()
        return render(request, 'repo/ds_size_err.html', context={
            'total': response.result.numFound,
            'results': response.result.docs
        })

    if mode == 'pid-list':
        response = query.field_limit('pid').cursor(rows=500)
        pid_list = '\n'.join(doc['pid'] for doc in response)
        return HttpResponse(pid_list, content_type='text/plain')


def size_range_json(request):
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    # use stats query to determine max size
    stats_query = solr.query().filter(type='object') \
                      .stats('master_size') \
                      .paginate(rows=0).execute()
    max_binary_size = int(stats_query.stats.stats_fields['master_size']['max'])

    size_query = response = solr.query().filter(type='object') \
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


def collection_treemap_json(request):
    # collection treemap, number of objects
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    facet_query = solr.query().filter(type='object').facet_by(fields=[
        "collection"]).paginate(rows=0)

    result = facet_query.execute()
    facets = result.facet_counts.facet_fields

    # get collection hierarchy for parent and label
    response = solr.query(
        solr.Q(content_model='info:fedora/emory-control:Collection-1.0') |
        solr.Q(content_model='info:fedora/emory-control:Collection-1.1')) \
       .field_limit(['pid', 'collection', 'label']) \
       .sort_by('id') \
       .cursor(rows=500)

    parents = {}
    labels = {}
    for doc in response:
        labels[doc['pid']] = doc['label']
        if 'collection' in doc:
            parents[doc['pid']] = doc['collection'][0]

    data = []
    info_prefix = 'info:fedora/'
    info_len = len(info_prefix)
    for collection_pid, count in facets['collection']:
        # strip of info:fedora/ prefix
        short_pid = collection_pid[info_len:]
        collection_data = {
            'id': collection_pid,
            'name': labels[short_pid],
            'value': count
        }
        if short_pid in parents:
            collection_data['parent'] = parents[short_pid]
        data.append(collection_data)
    return JsonResponse({'data': data})


def mimetype_treemap_json(request):
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    # mimetype by count of objects
    result = solr.query().facet_by(fields=[
        "mimetype"]).paginate(rows=0).execute()
    facets = result.facet_counts.facet_fields

    data = []
    parents = set()
    for mimetype, count in facets['mimetype']:
        if mimetype and '/' in mimetype:
            parent, subtype = mimetype.split('/', 1)
        else:
            parent = None
        parents.add(parent)
        data.append({'id': 'mimetype', 'value': count, 'name': mimetype,
                     'parent': parent})

    for parent in parents:
        data.append({'id': parent, 'name': parent})

    return JsonResponse({'data': data})


def mimetype_size_treemap_json(request):
    solr = scorched.SolrInterface(settings.SOLR_SERVER_URL)
    # get master datastream size, faceted on mimetype
    stats_query = solr.query().stats('master_size', facet='mimetype') \
                              .paginate(rows=0).execute()
    mimetype_stats = stats_query.stats.stats_fields['master_size']['facets']['mimetype']
# {% with stats.object_size.facets.state as status_stats %}

    data = []
    parents = set()
    # NOTE: overlapping logic with mimetype_treemap
    for mimetype, stats in mimetype_stats.iteritems():
        stats['sum']
        if mimetype and '/' in mimetype:
            parent, subtype = mimetype.split('/', 1)
            parents.add(parent)
        else:
            parent = None
        data.append({
            'id': 'mimetype', 'value': stats['sum'],
            'name': '%s (%s)' % (mimetype, filesizeformat(stats['sum'])),
            'parent': parent})

    for parent in parents:
        data.append({'id': parent, 'name': parent})

    return JsonResponse({'data': data})


def treemap(request, mode):
    if mode == 'collection':
        json_url = reverse('collection-treemap-json')
        title = 'Number of objects by collection'
    elif mode == 'mimetype':
        json_url = reverse('mimetype-treemap-json')
        title = 'Number of objects by master content mimetype'
    elif mode == 'mimetype-size':
        json_url = reverse('mimetype-size-treemap-json')
        title = 'Size of content by master mimetype'

    return render(request, 'repo/treemap.html', {
        'json_url': json_url, 'title': title})