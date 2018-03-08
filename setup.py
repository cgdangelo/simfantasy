from setuptools import setup, find_packages

setup(
    name='SimFantasy',
    version='1.0',
    packages=find_packages(),
    author='Charles D\'Angelo',
    author_email='c.g.dangelo@gmail.com',
    include_package_data=True,
    install_requires=[
        'numpy',
        'humanfriendly',
        'pandas',
        'bokeh',
    ],
    extras_require={
        'docs': [
            'sphinx-autodoc-typehints',
        ]
    }
)
