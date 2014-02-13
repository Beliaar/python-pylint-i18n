try:
    from logilab import astng
    from logilab.astng.node_classes import *
except ImportError:
    import astroid
    from astroid.node_classes import *

try:
    from pylint.interfaces import IAstroidChecker
except:
    # fallback to older pylint naming
    from pylint.interfaces import IASTNGChecker as IAstroidChecker

from pylint.checkers import BaseChecker

import string

def is_number(string):
    """Returns True if this string is a string representation of a number"""
    try:
        float(string)
        return True
    except ValueError:
        return False

def is_child_node(child, parent):
    """Returns True if child is an eventual child node of parent"""
    node = child
    while node is not None:
        if node == parent:
            return True
        node = node.parent
    return False


def _is_str(s):
    """
    Is this a string or a unicode string?
    """
    if isinstance(s, str):
        return True
    try:
        if isinstance(s, unicode):
            return True
    except NameError: # unicode not defined in Python 3
        pass
    return False


class MissingGettextChecker(BaseChecker):
    """
    Checks for strings that aren't wrapped in a _ call somewhere
    """
    
    __implements__ = IAstroidChecker

    name = 'missing_gettext'
    msgs = {
        'W9903': ('non-gettext-ed string %r',
                  'non-gettext-ed string',
                  "There is a raw string that's not passed through gettext"),
        }

    # this is important so that your checker is executed before others
    priority = -1 


    def visit_const(self, node):
        if not _is_str(node.value):
            return

        # Ignore some strings based on the contents.
        # Each element of this list is a one argument function. if any of them
        # return true for this string, then this string is ignored
        whitelisted_strings = [
            # ignore empty strings
            lambda x : x == '',

            # This string is probably used as a key or something, and should be ignored
            lambda x: len(x) > 3 and x.upper() == x,

            # pure number
            is_number,

            # URL, can't be translated
            lambda x: x.startswith("http://") or x.endswith(".html"),
            lambda x: x.startswith("https://") or x.endswith(".html"),
            
            # probably a regular expression
            lambda x: x.startswith("^") and x.endswith("$"),

            # probably a URL fragment
            lambda x: x.startswith("/") and x.endswith("/"),

            # Only has format specifiers and non-letters, so ignore it
            lambda x :not any([z in x.replace("%s", "").replace("%d", "") for z in string.ascii_letters]),

            # sending http attachment header
            lambda x: x.startswith("attachment; filename="),

            # sending http header
            lambda x: x.startswith("text/html; charset="),
        ]

        for func in whitelisted_strings:
            if func(node.value):
                return
        

        # Whitelist some strings based on the structure.
        # Each element of this list is a 2-tuple, class and then a 2 arg function.
        # Starting with the current string, and going up the parse tree to the
        # root (i.e. the whole file), for every whitelist element, if the
        # current node is an instance of the first element, then the 2nd
        # element is called with that node and the original string. If that
        # returns True, then this string is assumed to be OK.
        # If any parent node of this string returns True for any of these
        # functions then the string is assumed to be OK
        whitelist = [
            # {'shouldignore': 1}
            (Dict,    lambda curr_node, node: node in [x[0] for x in curr_node.items]),

            # dict['shouldignore']
            (Index,   lambda curr_node, node: curr_node.value == node),

            # Just a random doc-string-esque string in the code
            (Discard, lambda curr_node, node: curr_node.value == node),

            # X(attrs=dict(....))
            (Keyword, lambda curr_node, node: curr_node.arg == 'attrs' and isinstance(curr_node.value, CallFunc) and hasattr(curr_node.value.func, 'name') and curr_node.value.func.name == 'dict' ),
            # something() == 'string'
            (Compare, lambda curr_node, node: node == curr_node.ops[0][1]),
            # 'something' == blah()
            (Compare, lambda curr_node, node: node == curr_node.left),

            # Queryset functions, queryset.order_by('shouldignore')
            (CallFunc, lambda curr_node, node: isinstance(curr_node.func, Getattr) and curr_node.func.attrname in ['has_key', 'pop', 'order_by', 'strftime', 'strptime', 'get', 'select_related', 'values', 'filter', 'values_list']),

                
            # hasattr(..., 'should ignore')
            (CallFunc, lambda curr_node, node: curr_node.func.name in ['hasattr', 'getattr'] and curr_node.args[1] == node),
            # getChild of CEGUI windows
            (CallFunc, lambda curr_node, node: isinstance(curr_node.func, Getattr) and curr_node.func.attrname in ['getChild', ]),
        ]

        string_ok = False
        
        debug = False
        #debug = True
        curr_node = node
        if debug:
            import pdb ; pdb.set_trace()

        # we have a string. Go upwards to see if we have a _ function call
        try:
            while curr_node.parent is not None:
                if debug:
                    print(repr(curr_node)); print(repr(curr_node.as_string())) ; print(curr_node.repr_tree())
                if isinstance(curr_node, CallFunc):
                    if hasattr(curr_node, 'func') and hasattr(curr_node.func, 'name'):
                        if curr_node.func.name in ['_', 'ungettext', 'ungettext_lazy']:
                            # we're in a _() call
                            string_ok = True
                            break

                # Look at our whitelist
                for cls, func in whitelist:
                    if isinstance(curr_node, cls):
                        try:
                            # Ignore any errors from here. Otherwise we have to
                            # pepper the whitelist with loads of defensive
                            # hasattrs, which increase bloat
                            if func(curr_node, node):
                                string_ok = True
                                break
                        except:
                            pass

                curr_node = curr_node.parent

        except Exception as e:
            print(node, node.as_string())
            print(curr_node, curr_node.as_string())
            print(e)
            import pdb ; pdb.set_trace()
        
        if not string_ok:
            # we've gotten to the top of the code tree / file level and we
            # haven't been whitelisted, so add an error here
            self.add_message('W9903', node=node, args=node.value)

    
def register(linter):
    """required method to auto register this checker"""
    linter.register_checker(MissingGettextChecker(linter))
        

