tagname='0.1.4'
git tag --delete ${tagname}
git tag ${tagname}   -m "first pip version"
git push origin :refs/tags/${tagname}
git push --tags origin main
rm dist/*
python3 -m build
twine upload -r pypi dist/*

