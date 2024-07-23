tagname='0.1.0'
git tag --delete ${tagname}
git tag ${tagname}   -m "first pip version"
git push origin :refs/tags/${tagname}
git push --tags origin main
python3 -m build
twine upload -r pypi dist/*

