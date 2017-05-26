# Query Translators

These modules translate (unparse) RQL Abstract Syntax Tree into database query languages
Presently, a subset of RQL is supported for mongodb query objects

# Mongodb
`mongodb.unparse` accepts an RQL AST and returns a python dictionary that, when converted to JSON, is a valid MongoDB query object.

eg.
```
{'name': 'lt', 'args': ['age', 25]}

becomes

{'age': {'$lt': 25}}

```

The following subset of RQL is supported ✅.
(❌ are [not implemented] not implemented)

❌ sort [not implemented]
  > `sort(<+|-><property)` - Sorts the returned query result by the given property. The order of sort is specified by the prefix (+ for ascending, - for descending) to property. To sort by foo in ascending order:
  > `sort(+foo)`
  > One can also do multiple property sorts. To sort by price in ascending order and rating in descending order:
  > `sort(+price,-rating)`

❌ select [not implemented]
  > `select(<property>)` - Returns a query result where each item is value of the property specified by the argument
  > `select(<property>,<property>,...)` - Trims each object down to the set of properties defined in the arguments


❌ aggregate [not implemented]
  > `aggregate(<property|operator>,...)` - The aggregate function can be used for aggregation, it aggregates the result set, grouping by objects that are distinct for the provided properties, and then reduces the remaining other property values using the provided operator. To calculate the sum of sales for each department:
  > `aggregate(departmentId,sum(sales))``

❌ distinct [not implemented]
  > `distinct()` - Returns a result set with duplicates removed


✅ in
  > `in(<property>,<array-of-values>)` - Filters for objects where the specified property's value is in the provided array


❌ contains [not implemented]
  > `contains(<property>,<value | array-of-values>)` - Filters for objects where the specified property's value is an array and the array contains the provided value or contains a value in the provided array


❌ limit [not implemented]
  > `limit(start,count)` - Returns a limited range of records from the result set. The first parameter indicates the starting offset and the second parameter indicates the number of records to return.


✅ and
  > `and(<query>,<query>,...)` - Returns a query result set applying all the given operators to constrain the query


✅ or
  > `or(<query>,<query>,...)` - Returns a union result set of the given operators


✅ eq
  > `eq(<property>,<value>)` - Filters for objects where the specified property's value is equal to the provided value


✅ lt
  > `lt(<property>,<value>)` - Filters for objects where the specified property's value is less than the provided value


✅ le
  > `le(<property>,<value>)` - Filters for objects where the specified property's value is less than or equal to the provided value


✅ gt
  > `gt(<property>,<value>)` - Filters for objects where the specified property's value is greater than the provided value


✅ ge
  > `ge(<property>,<value>)` - Filters for objects where the specified property's value is greater than or equal to the provided value


✅ ne
  > `ne(<property>,<value>)` - Filters for objects where the specified property's value is not equal to the provided value


❌ sum [not implemented]
  > `sum(<property?>)` - Finds the sum of every value in the array or if the property argument is provided, returns the sum of the value of property for every object in the array


❌ mean [not implemented]
  > `mean(<property?>)` - Finds the mean of every value in the array or if the property argument is provided, returns the mean of the value of property for every object in the array


❌ max [not implemented]
  > `max(<property?>)` - Finds the maximum of every value in the array or if the property argument is provided, returns the maximum of the value of property for every object in the array


❌ min [not implemented]
  > `min(<property?>)` - Finds the minimum of every value in the array or if the property argument is provided, returns the minimum of the value of property for every object in the array


❌ recurse [not implemented]
  > `recurse(<property?>)` - Recursively searches, looking in children of the object as objects in arrays in the given property value
