# RQL-Python


# Usage
`convert_to_mongo(<rql string>)`
Takes an rql string and produces a mondodb query dictionary.

## parser.parse
Port of the [Official Resource Query Language Tools](https://github.com/persvr/rql)

**WARNING**
Think twice before trying to make big changes to this - It's not that nice!
Regex and nesting a-hoy. You've been warned.
May be better to reimplement.

### Tests
ported tests for `parser.parse` do not use unittest.

Use `nosetest` / `nose2` / `green` or similar if you want to run all the `parser.parse` tests


## query.mongodb.unparse
Translates between the abstract syntax tree outputted by `parser.parse` and mongodb query dictionaries.

### Tests
Tests for `uery.mongodb.unparse` use unittest so `python -m unittest discover -s .` (as used in by make deb) will work.
