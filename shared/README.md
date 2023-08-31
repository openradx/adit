# Django shared

## About

This folder contains the shared code between ADIT and RADIS. The source code is added as a Git subtree to the `shared` folder.

## Git subtree usage

```python
# Make code initially available in another repository
git remote add -f shared https://github.com/radexperts/django-shared.git
git subtree add --prefix shared shared main --squash

# After that pull updates from the shared repository
git subtree pull --prefix shared shared main --squash

# Or push updates to the shared repository
git subtree push --prefix shared shared main
```

## License

- GPL 3.0 or later
