from django.db.models import Field
from django.db.models.lookups import IContains


class UnicodeIContains(IContains):
    """icontains, который работает и для кириллицы в SQLite (UPPER с обеих сторон)."""

    lookup_name = "u_icontains"

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return "UPPER(%s) LIKE UPPER(%s) ESCAPE '\\'" % (lhs, rhs), params


Field.register_lookup(UnicodeIContains)
