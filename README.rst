Thomas
======

Thomas is many things, among them:

* A framework to build a streaming platform by inputting, processing and outputting files.
* A segmented downloader that makes it possible to play file while downloading.

Install
-------

From pypi (stable):
::

    pip install thomas


From GitHub (develop):
::

    virtualenv thomas-env
    thomas-env/bin/pip install git+https://github.com/JohnDoee/thomas.git#develop


Upgrade from previous version
-----------------------------

Upgrading from Github (develop)
::

    thomas-env/bin/pip install git+https://github.com/JohnDoee/thomas.git#develop --upgrade --force-reinstall

Instructions
------------

Start by installing.

Then get downloading
::
    thomas http://rbx.proof.ovh.net/files/100Mio.dat

See more commands by looking at ``thomas -h``

License
-------

MIT, see LICENSE
