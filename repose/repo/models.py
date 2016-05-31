from __future__ import unicode_literals
from collections import OrderedDict

from eulfedora.models import DigitalObject, Relation
from eulfedora.rdfns import relsext


class GenericObject(DigitalObject):

    collection = Relation(relsext.isMemberOfCollection, type='self')
    constituent_of = Relation(relsext.isConstituentOf, type='self')
    part_of = Relation(relsext.isPartOf, type='self')

    def index_data(self):
        data = OrderedDict(super(GenericObject, self).index_data())
        binary_size = 0
        xml_size = 0
        # preliminary object size, based on size of the foxml
        response = self.api.getObjectXML(self.pid)
        try:
            # use content-length header if present
            object_size = int(response.headers['Content-Length'])
        except KeyError:
            # otherwise, get the size from actual content
            object_size = len(response.content)
        # number of binary datastream versions on this object
        binary_count = 0

        for ds in self.ds_list:
            dsobj = self.getDatastreamObject(ds)
            for version in dsobj.history().versions:
                # FIXME: should external datastreams be included here?
                if dsobj.mimetype in ['text/xml', 'application/xml',
                                      'application/rdf+xml']:
                    xml_size += version.size
                else:
                    binary_size += version.size
                    # only include managed datastreams in binary count
                    if version.control_group == 'M':
                        binary_count += 1

                # if datastream is versioned, count it towards object size
                if version.control_group == 'M':
                    object_size += version.size

        data.update({
            # estimated size for entire object
            'object_size': object_size,
            'binary_size': binary_size,
            'binary_count': binary_count,
            'xml_size': xml_size,
        })
        data.update(self.master_access_info())
        return data

    def index_data_descriptive(self):
        # do we need any descriptive data indexed?
        # *maybe* for stats on objects with/without ARKs...
        return {}

    def index_data_relations(self):
        # existing data rels is useful; includes content models
        # and collection membership
        data = OrderedDict(super(GenericObject, self).index_data_relations())
        # handle any non-fedora rels we care about
        # translate custom etd rels into something more consistent
        for pred, obj in self.rels_ext.content.predicate_objects(self.uriref):
            if str(pred).endswith('isOriginalOf') or \
               str(pred).endswith('isPDFOf'):
                data['isConstituentOf'] = [str(obj)]
               # TODO: other etd rels here too: supplement / author info?

        # index any collection membership through other objects
        # TODO: simplify this and just use collection
        # NOTE: default data relations uses'isMemberOfCollection'
        # storing as collection to simplify solr searching
        data['collection'] = self.get_collections(data)

        return data

    cmodels = {
        'video': 'info:fedora/emory-control:Video-1.0',
        'audio': 'info:fedora/emory-control:EuterpeAudio-1.0',
        'disk_image': 'info:fedora/emory-control:DiskImage-1.0',
        'etd_file': 'info:fedora/emory-control:EtdFile-1.0',
        'image': 'info:fedora/emory-control:Image-1.0',
        'volume': 'info:fedora/emory-control:ScannedVolume-1.0',
        'oe_publication': 'info:fedora/emory-control:PublishedArticle-1.0',
    }
    # todo: include old rushdie data

    master_ds = {
        'video': 'VIDEO',
        'audio': 'AUDIO',
        'disk_image': 'content',
        'etd_file': 'FILE',
        'image': 'source-image',
        'volume': 'PDF',
        'oe_publication': 'content'
    }
    access_ds = {
        'video': 'CompressedVideo',
        'audio': 'CompressedAudio',
    }

    def content_type(self):
        for ctype, cmodel in self.cmodels.iteritems():
            if self.has_model(cmodel):
                return ctype

    def master_access_info(self):
        ctype = self.content_type()
        info = OrderedDict()
        if ctype in self.master_ds:
            master = self.getDatastreamObject(self.master_ds[ctype])
            # not all objects of a given type have a
            if master.exists:
                if master.size is not None:
                    info['master_size'] = master.size
                # primary mimetype for the object
                info['mimetype'] = master.mimetype

        if ctype in self.access_ds:
            access = self.getDatastreamObject(self.access_ds[ctype])
            if access.exists and access.size is not None:
                info['access_size'] = access.size

        return info

    def get_collections(self, rels=None):
        collections = []
        # collections & parents should exist in production,
        # but may not in dev/qa, so check that they exist before chaining
        if self.collection:
            if self.collection.exists:
                collections.append(self.collection.uri)
                # collections can nest, and we want the all
                collections.extend(self.collection.get_collections())
        if rels is not None:
            parent = None
            # includes custom etd relations that have been made more consistent
            if 'isConstituentOf' in rels:
                parent = self.get_object(rels['isConstituentOf'][0])

            if 'isPartOf' in rels:
                parent = self.get_object(rels['isPartOf'][0])

            if parent is not None and parent.exists:
                collections.extend(parent.get_collections())
        else:
            if self.constituent_of:
                collections.extend(self.constituent_of.get_collections())
            if self.part_of:
                collections.extend(self.part_of.get_collections())

        return collections
