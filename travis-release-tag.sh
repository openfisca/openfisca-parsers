# On travis CI, we use the openfisca_bot key. It is locally decrypted on the CI environment from openfisca_bot.enc before deploying.
set -x

version=`python setup.py --version`
eval "$(ssh-agent -s)" #start the ssh agent
if [ -e openfisca_bot ]
then
	chmod 400 ./openfisca_bot
	ssh-add ./openfisca_bot
else
    set +x
    ls
    echo "Could not find openfisca_bot private key."
    exit 1
fi
git tag $version
git push git@github.com:openfisca/openfisca-parsers --tags
