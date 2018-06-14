from setuptools import setup, find_packages

version = '2.3'

requires = [
    'setuptools',
    'openprocurement.contracting.core',  # TODO set version
    'openprocurement.tender.esco',
]
test_requires = requires + [
    'webtest',
    'python-coveralls',
    'munch',
]
docs_requires = requires + [
    'sphinxcontrib-httpdomain',
]

entry_points = {
    'openprocurement.contracting.core.plugins': [
        'contract.esco = openprocurement.contracting.esco.includeme:includeme'
    ]
}

setup(name='openprocurement.contracting.esco',
      version=version,
      description="",
      long_description=open("README.rst").read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
          "License :: OSI Approved :: Apache Software License",
          "Programming Language :: Python",
      ],
      keywords='',
      author='Quintagroup, Ltd.',
      author_email='info@quintagroup.com',
      url='https://github.com/openprocurement/openprocurement.contracting.esco',
      license='Apache License 2.0',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['openprocurement', 'openprocurement.contracting'],
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=test_requires,
      extras_require={'test': test_requires, 'docs': docs_requires},
      test_suite="openprocurement.contracting.esco.tests.main.suite",
      entry_points=entry_points
      )
