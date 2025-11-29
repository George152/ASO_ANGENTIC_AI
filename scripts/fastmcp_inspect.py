import fastmcp
from fastmcp import types
print('fastmcp path', fastmcp.__file__)
print('has TextContent', hasattr(types, 'TextContent'))
print('types module at', types.__file__)
print([cls for cls in dir(types) if 'Content' in cls])
