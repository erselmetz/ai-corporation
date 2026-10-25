import pytest
from app.application.services.exact_math import calculate,solve_equation,convert_units,ExactMathError


@pytest.mark.parametrize('expression,answer',[
    ('0.1+0.2','0.3'),('1/3','1/3'),('1/8','0.125'),('-7//2','-4'),
    ('0.1234567890123456789+0.0000000000000000001','0.123456789012345679'),('2**-3','0.125')])
def test_exact_arithmetic(expression,answer):assert calculate(expression)==answer


@pytest.mark.parametrize('expression',[
    "__import__('os').system('whoami')",'x.real','[1]*100000','True','1/0',
    '10**13','2**0.5','9**9**9','1e999','0.1' * 100,'1e-9999'])
def test_rejects_unsafe_or_unbounded_arithmetic(expression):
    with pytest.raises(ExactMathError):calculate(expression)


@pytest.mark.parametrize('equation,answer',[
    ('2*x+1=4','x = 1.5'),('x*x-5*x+6=0','x = 2, 3'),
    ('x**2=2','x = (0 ± sqrt(8)) / (2)'),('x=x','All x satisfy the equation.'),
    ('x=x+1','No solution.'),('x*x=-1','No real solution (complex roots are outside this tool).')])
def test_exact_bounded_equations(equation,answer):assert solve_equation(equation)==answer


@pytest.mark.parametrize('equation',['x**3=1','x/(x+1)=2','sin(x)=0','x=1=2','y=1','x*x*x=1'])
def test_rejects_unsupported_equations(equation):
    with pytest.raises(ExactMathError):solve_equation(equation)


@pytest.mark.parametrize('value,source,target,answer',[
    ('1','in','cm','2.54 cm'),('32','F','C','0 C'),('100','C','F','212 F'),
    ('36','km/h','m/s','10 m/s'),('1/2','h','min','30 min')])
def test_exact_unit_conversions(value,source,target,answer):assert convert_units(value,source,target)==answer


@pytest.mark.parametrize('value,source,target',[('1','m','s'),('-274','C','K'),('1','os.system','m')])
def test_conversion_boundaries(value,source,target):
    with pytest.raises(ExactMathError):convert_units(value,source,target)
