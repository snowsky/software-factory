#!/usr/bin/env python

import os
import sys
import yaml

workdir = "/tmp/nodepool"
main = 'nodepool.yaml'
images = 'images.yaml'
labels = 'labels.yaml'


def merge():
    conf = yaml.safe_load(file(os.path.join(workdir, main), 'r'))
    images_conf = yaml.safe_load(file(os.path.join(workdir, images), 'r'))
    labels_conf = yaml.safe_load(file(os.path.join(workdir, labels), 'r'))

    for provider in images_conf:
        for defined_provider in conf['providers']:
            if provider['provider'] == defined_provider['name']:
                defined_provider['images'] = provider['images']

    conf['labels'] = labels_conf['labels']
    return yaml.dump(conf, default_flow_style=False)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Please provide the target filename"
        sys.exit(1)
    else:
        try:
            out = merge()
        except Exception as err:
            print err
            sys.exit(1)

        print out
        file(os.path.join(workdir, sys.argv[1]), 'w').write(out)