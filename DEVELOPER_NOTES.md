**Repose Quick Setup Guide**
*Nov 1 2016*
*Yang Li*

This setup guide offers basic instructions about how to install Repose.

**GitHub Repoistory Link**
https://github.com/emory-lits-labs/repose/tree/develop

**Steps**
Please clone the repo to a local directory:
`git clone git@github.com:emory-lits-labs/repose.git`

Checkout to develop branch because currently there is nothing in the master branch:
`git checkout develop`

Create a Python virtual environment for repose:
`mkvirtualenv repose`

Once the virtual environment is created and activated, we could update the pip:
`pip install pip —upgrade`

Then we could use the latest pip to install all the dependencies:
`pip install -r requirements.txt`

Get `localsettings.py` from the settings repo:
`localsettings.py`

And add a secret key to the `localsettings.py`, and this can be generated with:
`rake secret`

Run pending migrations:
`./manage.py migrate`

Run server:
`./manage.py runserver`
