"""Bounded exact arithmetic. No eval, dynamic imports or symbolic string parser."""
import ast
from fractions import Fraction
from math import isqrt
from decimal import Decimal, InvalidOperation


class ExactMathError(ValueError):
    pass


def bounded(value):
    if abs(value)>10**12 or value.numerator.bit_length()>160 or value.denominator.bit_length()>160:
        raise ExactMathError('Math result exceeds the supported bounds.')
    return value


def tree(text):
    if not isinstance(text,str) or not text.strip() or len(text)>256:
        raise ExactMathError('Math input must be 1–256 characters.')
    try: root=ast.parse(text,mode='eval')
    except (SyntaxError,ValueError): raise ExactMathError('Enter an explicit arithmetic expression.') from None
    if len(list(ast.walk(root)))>40: raise ExactMathError('Math expression is too complex.')
    for node in ast.walk(root):
        if isinstance(node,ast.Constant): node.exact_literal=ast.get_source_segment(text,node)
    return root.body


def number(node):
    if isinstance(node,ast.Constant) and type(node.value) in (int,float):
        # Decimal source spelling is exact, including scientific notation.
        try:
            literal=Decimal(getattr(node,'exact_literal',str(node.value)))
            if not literal.is_finite() or abs(literal.as_tuple().exponent)>48 or len(literal.as_tuple().digits)>48:
                raise ExactMathError('Number precision or exponent exceeds the supported bounds.')
            return bounded(Fraction(literal))
        except (ValueError,OverflowError,InvalidOperation): pass
    raise ExactMathError('Only bounded numbers and supported arithmetic are allowed.')


def evaluate(node):
    if isinstance(node,ast.Constant): return number(node)
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
        value=evaluate(node.operand); return value if isinstance(node.op,ast.UAdd) else -value
    if not isinstance(node,ast.BinOp): raise ExactMathError('Names, calls and attributes are not allowed.')
    a,b=evaluate(node.left),evaluate(node.right)
    try:
        if isinstance(node.op,ast.Add): value=a+b
        elif isinstance(node.op,ast.Sub): value=a-b
        elif isinstance(node.op,ast.Mult): value=a*b
        elif isinstance(node.op,ast.Div): value=a/b
        elif isinstance(node.op,ast.FloorDiv): value=Fraction(a//b)
        elif isinstance(node.op,ast.Mod): value=a%b
        elif isinstance(node.op,ast.Pow) and b.denominator==1 and abs(b)<=12: value=a**int(b)
        else: raise ExactMathError('Unsupported operator or exponent; use integer powers from -12 to 12.')
        return bounded(value)
    except ArithmeticError: raise ExactMathError('Math expression is undefined.') from None


def display(value):
    """Exact finite decimals; recurring results stay rational."""
    value=Fraction(value); denominator=value.denominator; twos=fives=0
    while denominator%2==0: denominator//=2; twos+=1
    while denominator%5==0: denominator//=5; fives+=1
    places=max(twos,fives)
    if denominator!=1 or places>24: return str(value)
    sign='-' if value<0 else ''; scaled=abs(value.numerator)*(10**places//value.denominator)
    if not places: return sign+str(scaled)
    digits=str(scaled).zfill(places+1)
    return sign+(digits[:-places]+'.'+digits[-places:]).rstrip('0').rstrip('.')


def calculate(expression):
    return display(evaluate(tree(expression)))


def polynomial(node):
    """Only x and degree <= 2, with rational coefficients; division by constants."""
    if isinstance(node,ast.Name) and node.id=='x': return (Fraction(0),Fraction(1),Fraction(0))
    if isinstance(node,ast.Constant): return (number(node),Fraction(0),Fraction(0))
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
        p=polynomial(node.operand);return p if isinstance(node.op,ast.UAdd) else tuple(-v for v in p)
    if not isinstance(node,ast.BinOp): raise ExactMathError('Use a polynomial in x, degree at most two.')
    a=polynomial(node.left)
    if isinstance(node.op,ast.Pow):
        exponent=evaluate(node.right)
        if exponent.denominator!=1 or not 0<=exponent<=2: raise ExactMathError('Polynomial powers must be 0, 1 or 2.')
        result=(Fraction(1),Fraction(0),Fraction(0))
        for _ in range(int(exponent)): result=multiply(result,a)
        return result
    b=polynomial(node.right)
    if isinstance(node.op,(ast.Add,ast.Sub)):
        sign=1 if isinstance(node.op,ast.Add) else -1
        return tuple(bounded(x+sign*y) for x,y in zip(a,b))
    if isinstance(node.op,ast.Mult): return multiply(a,b)
    if isinstance(node.op,ast.Div) and b[1:]==(0,0) and b[0]: return tuple(bounded(x/b[0]) for x in a)
    raise ExactMathError('Use polynomial arithmetic and divide only by nonzero constants.')


def multiply(a,b):
    result=[Fraction(0)]*5
    for i,x in enumerate(a):
        for j,y in enumerate(b):result[i+j]=bounded(result[i+j]+bounded(x*y))
    if any(result[3:]):raise ExactMathError('Polynomial degree exceeds two.')
    return tuple(result[:3])


def solve_equation(equation):
    if not isinstance(equation,str) or len(equation)>256 or equation.count('=')!=1:
        raise ExactMathError('Enter one equation in x, with one equals sign (degree at most two).')
    left,right=equation.split('='); a=polynomial(tree(left.strip()));b=polynomial(tree(right.strip()))
    c,b,a=(bounded(x-y) for x,y in zip(a,b))
    if not a:
        if not b:return 'All x satisfy the equation.' if not c else 'No solution.'
        return 'x = '+display(bounded(-c/b))
    discriminant=bounded(b*b-4*a*c)
    if discriminant<0:return 'No real solution (complex roots are outside this tool).'
    numerator=isqrt(discriminant.numerator);denominator=isqrt(discriminant.denominator)
    if numerator*numerator==discriminant.numerator and denominator*denominator==discriminant.denominator:
        root=Fraction(numerator,denominator);values=sorted({bounded((-b-root)/(2*a)),bounded((-b+root)/(2*a))})
        return 'x = '+', '.join(display(value) for value in values)
    return f'x = ({display(-b)} ± sqrt({display(discriminant)})) / ({display(2*a)})'


# dimension, multiplier, offset to canonical SI; no arbitrary unit grammar.
UNITS={
    'm':('length',Fraction(1),0),'km':('length',Fraction(1000),0),'cm':('length',Fraction(1,100),0),
    'mm':('length',Fraction(1,1000),0),'in':('length',Fraction(127,5000),0),'ft':('length',Fraction(381,1250),0),
    'mi':('length',Fraction(201168,125),0),'s':('time',Fraction(1),0),'min':('time',Fraction(60),0),
    'h':('time',Fraction(3600),0),'kg':('mass',Fraction(1),0),'g':('mass',Fraction(1,1000),0),
    'lb':('mass',Fraction(45359237,100000000),0),'m/s':('speed',Fraction(1),0),
    'km/h':('speed',Fraction(5,18),0),'K':('temperature',Fraction(1),0),
    'C':('temperature',Fraction(1),Fraction(27315,100)),
    'F':('temperature',Fraction(5,9),Fraction(45967,180)),
}


def convert_units(value,source_unit,target_unit):
    if source_unit not in UNITS or target_unit not in UNITS:raise ExactMathError('Unsupported unit. Choose a listed unit symbol.')
    source,target=UNITS[source_unit],UNITS[target_unit]
    if source[0]!=target[0]:raise ExactMathError('Choose units of the same physical dimension.')
    amount=evaluate(tree(value));canonical=bounded(amount*source[1]+source[2])
    if source[0]=='temperature' and canonical<0:raise ExactMathError('Temperature is below absolute zero.')
    return display(bounded((canonical-target[2])/target[1]))+' '+target_unit
