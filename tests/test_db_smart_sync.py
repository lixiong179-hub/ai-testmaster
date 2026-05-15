from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy import DefaultClause
from sqlalchemy.ext.declarative import declarative_base

from app.db.smart_sync import DatabaseSyncTool


class TestResolveSqlDefault:
    def setup_method(self):
        self.tool = DatabaseSyncTool()

    def test_server_default_string_zero(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't1'
            id = Column(Integer, primary_key=True)
            flag = Column(Boolean, nullable=False, default=False, server_default='0')
        col = Base.metadata.tables['t1'].columns['flag']
        assert self.tool._resolve_sql_default(col) == '0'

    def test_server_default_text_zero(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't2'
            id = Column(Integer, primary_key=True)
            flag = Column(Boolean, server_default=text('0'))
        col = Base.metadata.tables['t2'].columns['flag']
        assert self.tool._resolve_sql_default(col) == '0'

    def test_server_default_text_false(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't3'
            id = Column(Integer, primary_key=True)
            flag = Column(Boolean, server_default=text('false'))
        col = Base.metadata.tables['t3'].columns['flag']
        assert self.tool._resolve_sql_default(col) == 'false'

    def test_python_default_false_boolean(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't4'
            id = Column(Integer, primary_key=True)
            flag = Column(Boolean, default=False)
        col = Base.metadata.tables['t4'].columns['flag']
        assert self.tool._resolve_sql_default(col) == '0'

    def test_python_default_true_boolean(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't5'
            id = Column(Integer, primary_key=True)
            flag = Column(Boolean, default=True)
        col = Base.metadata.tables['t5'].columns['flag']
        assert self.tool._resolve_sql_default(col) == '1'

    def test_python_default_integer(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't6'
            id = Column(Integer, primary_key=True)
            count = Column(Integer, default=0)
        col = Base.metadata.tables['t6'].columns['count']
        assert self.tool._resolve_sql_default(col) == '0'

    def test_python_default_string(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't7'
            id = Column(Integer, primary_key=True)
            name = Column(String(50), default='unknown')
        col = Base.metadata.tables['t7'].columns['name']
        assert self.tool._resolve_sql_default(col) == "'unknown'"

    def test_no_default(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't8'
            id = Column(Integer, primary_key=True)
            name = Column(String(50), nullable=True)
        col = Base.metadata.tables['t8'].columns['name']
        assert self.tool._resolve_sql_default(col) is None

    def test_server_default_prioritized_over_python_default(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't9'
            id = Column(Integer, primary_key=True)
            flag = Column(Boolean, default=True, server_default='0')
        col = Base.metadata.tables['t9'].columns['flag']
        assert self.tool._resolve_sql_default(col) == '0'

    def test_server_default_current_timestamp(self):
        Base = declarative_base()
        class M(Base):
            __tablename__ = 't10'
            id = Column(Integer, primary_key=True)
            created = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
        col = Base.metadata.tables['t10'].columns['created']
        assert self.tool._resolve_sql_default(col) == 'CURRENT_TIMESTAMP'