# Shared code

This folder contains shared code between ADIT and RADIS, mainly account and authentication stuff.

The code is added to ADIT and RADIS as a git subtree:
`git subtree add --prefix adit/shared shared main --squash`

Push updates to shared:
`git subtree push --prefix adit/shared shared main`

Pull updates from shared:
`git subtree pull --prefix adit/shared shared main --squash`

## License

- GPL 3.0 or later
