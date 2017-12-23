Thomas
======

Thomas amplifies download speed by using parallel downloads similar to Axel or another
download manager that uses segmented downloads.
Thomas splits up the file like bittorrent instead of equal parts, this optimizes for reading while
downloading instead of easy development.

Requirements
------------

- Python

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

Or use it as an http "proxy"
::
    thomas --serve http
    wget http://127.0.0.1:8080/?url=http://rbx.proof.ovh.net/files/100Mio.dat

See more commands by looking at ``thomas -h``

License
-------

MIT, see LICENSE
