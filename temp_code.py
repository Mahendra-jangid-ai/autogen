class A:
    def method_a(self, a, b): 
        """Example method in class A."""
        print(f"Method A called with a={a}, b={b}")
        return a + b

class B(A):
    def method_b(self, b, c): 
        """Example method in class B."""
        print(f"Method B called with b={b}, c={c}")
        return b * c

a = A()  
b = B()  

print(a.method_a(10, 5))  
print(b.method_b(2, 7))  
print(b.method_a(3,4)) 