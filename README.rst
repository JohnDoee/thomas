Thomas
======

Thomas is a parallel HTTP downloading client intended to work as an alternativ to Axel.

Requirements
------------

- Python

Install
-------

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
    thomas-env/bin/thomas http://rbx.proof.ovh.net/files/100Mio.dat

See more commands by looking at ``thomas-env/bin/thomas -h``

License
-------

MIT, see LICENSE
