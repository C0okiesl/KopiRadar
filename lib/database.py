import os
import json
import logging
import traceback
from datetime import datetime
from lib.constants import _ROOT


log = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, Column, not_
    from sqlalchemy.dialects.mysql import INTEGER as Integer
    from sqlalchemy import String, Boolean, Float, DateTime, Enum
    from sqlalchemy import ForeignKey, Text, Index, Table
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.exc import SQLAlchemyError, IntegrityError
    from sqlalchemy.orm import sessionmaker, relationship, joinedload
    from sqlalchemy.ext.hybrid import hybrid_property
    Base = declarative_base()
except ImportError as e:
    log.error("Import Error: {0}".format(e))

chatid_filters = Table(
    "chatid_filters", Base.metadata,
    Column("chat_id", Integer, ForeignKey("chatids.id")),
    Column("filter_id", Integer, ForeignKey("filters.id"))
)

chatid_locations = Table(
    "chatid_locations", Base.metadata,
    Column("chat_id", Integer, ForeignKey("chatids.id")),
    Column("location_id", Integer, ForeignKey("locations.id"))
)

chatid_favs = Table(
    "chatid_favs", Base.metadata,
    Column("chat_id", Integer, ForeignKey("chatids.id")),
    Column("fav_id", Integer, ForeignKey("favs.id"))
)

chatid_history = Table(
    "chatid_history", Base.metadata,
    Column("chat_id", Integer, ForeignKey("chatids.id")),
    Column("history_id", Integer, ForeignKey("history.id"))
)

class ChatID(Base):
    """ Store the chatids and location"""
    __tablename__ = "chatids"

    id = Column(Integer(), primary_key=True)
    chatid = Column(Integer(unsigned=True), nullable=False, unique=True)
    lat = Column(Float(), nullable=False)
    lng = Column(Float(), nullable=False)
    filter_switch = Column(Integer, nullable=False)

    filters     = relationship("Filter", secondary=chatid_filters, single_parent=True, backref="chatids")
    locations   = relationship("Location", secondary=chatid_locations, single_parent=True, backref="chatids")
    favs        = relationship("Fav", secondary=chatid_favs, single_parent=True, backref="chatids")
    history      = relationship("History", secondary=chatid_history, single_parent=True, backref="chatids")


    def __repr__(self):
        return "<ChatID('{0}', '{1}', '{2}', '{3}')".format(self.id, self.chatid, self.lat, self.lng)

    def __init__(self, chatid, lat, lng):
        self.chatid         = int(chatid)
        self.lat            = float(lat)
        self.lng            = float(lng)
        self.filter_switch  = 0

class Filter(Base):
    __tablename__ = "filters"

    id = Column(Integer(), primary_key=True)
    name = Column(String(255), nullable=False)

    def __repr__(self):
        return "<Filter('{0}', '{1}')".format(self.id, self.name)

    def __init__(self, name):
        self.name = name

class Fav(Base):
    __tablename__ = "favs"

    id = Column(Integer(), primary_key=True)
    name = Column(String(255), nullable=False)

    def __repr__(self):
        return "<Fav('{0}', '{1}')".format(self.id, self.name)

    def __init__(self, name):
        self.name = name

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer(), primary_key=True)
    name = Column(String(255), nullable=False)
    lat = Column(Float(), nullable=False)
    lng = Column(Float(), nullable=False)

    def __repr__(self):
        return "<Location({0}, {1}, {2}, {3})".format(self.id, self.name, self.lat, self.lng)

    def __init__(self, name, lat, lng):
        self.name = name
        self.lat = float(lat)
        self.lng = float(lng)

class History(Base):
    __tablename__ = "history"

    id = Column(Integer(), primary_key=True)
    name        = Column(String(255), nullable=False)
    lat         = Column(Float(), nullable=False)
    lng         = Column(Float(), nullable=False)
    expire      = Column(String(255), nullable=False)

    def __repr__(self):
        return "<History({0}, {1}, {2}, {3}, {4})".format(self.id, self.name, self.lat, self.lng, self.expire)

    def __init__(self, name, lat, lng, expire):
        self.name = name
        self.lat = float(lat)
        self.lng = float(lng)
        self.expire = expire

class SpecialLocation(Base):
    __tablename__ = "speciallocations"

    id          = Column(Integer(), primary_key=True)
    name        = Column(String(255), nullable=False)
    minlat      = Column(Float(), nullable=False)
    maxlat      = Column(Float(), nullable=False)
    minlng      = Column(Float(), nullable=False)
    maxlng      = Column(Float(), nullable=False)

    def __repr__(self):
        return "<Special Location({0}, {1}, {2}, {3})".format(self.id, self.name, self.lat, self.lng)

    def __init__(self, name, minlat, maxlat, minlng, maxlng):
        self.name = name
        self.minlat = float(minlat)
        self.maxlat = float(maxlat)
        self.minlng = float(minlng)
        self.maxlng = float(maxlng)


class Database(object):
    def __init__(self):
        db_file     = os.path.join(_ROOT, "db", "kopiradar.db")
        if not os.path.exists(db_file):
            db_dir = os.path.dirname(db_file)
            if not os.path.exists(db_dir):
                try:
                     os.makedirs(db_dir)
                except:
                    log.error("Error in making {0}".format(db_dir))

        self._connect_database("sqlite:///%s" % db_file)

        try:
            Base.metadata.create_all(self.engine)
        except:
            log.error("UNable to create/connect to database")

        self.Session = sessionmaker(bind=self.engine)

    def _connect_database(self, connection_string):
        self.engine = create_engine(connection_string, connect_args={"check_same_thread": False})

    def _get_or_create(self, session, model, **kwargs):
        instance = session.query(model).filter_by(**kwargs).first()
        return instance or model(**kwargs)

    def get_all_chatid(self):
        session = self.Session()
        chatids = session.query(ChatID)
        result = []
        for row in chatids:
            result.append(row.chatid)
        return result

    def get_all_speciallocation(self):
        session = self.Session()
        x = session.query(SpecialLocation)
        result = []
        for row in x:
            result.append(row.name)
        return result

    def get_currentlocation(self, chatid):
        session = self.Session()
        tchatid  = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        return (float(tchatid.lat), float(tchatid.lng))

    ##### Get all  BY Chat ID ######
    def get_filterswitch(self, chatid):
        session = self.Session()
        tchatid  = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        return int(tchatid.filter_switch)

    def get_filters_by_chatid(self, chatid):
        session = self.Session()
        chatid = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        tfilter = chatid.filters
        return tfilter

    def get_favs_by_chatid(self, chatid):
        session = self.Session()
        chatid = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        tfavs = chatid.favs
        return tfavs

    def get_locations_by_chatid(self, chatid):
        session = self.Session()
        chatid = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        tlocations = chatid.locations
        return tlocations

    def get_history_by_chatid(self, chatid):
        session = self.Session()
        chatid = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        thistory = chatid.history
        return thistory

    #### Update by CHAT ID#####
    def update_current_location(self, chatid, lat, lng):
        session = self.Session()
        chatid = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        success = False
        try:
            chatid.lat = float(lat)
            chatid.lng = float(lng)
            session.commit()
            success = True
        except:
            log.error("Some error happens")
            session.rollback()
        finally:
            session.close()
            return success

    def update_filter_switch(self, chatid, switch):
        session = self.Session()
        chatid = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        success = False
        try:
            chatid.filter_switch = switch
            session.commit()
            success = True
        except:
            log.error("Some error happens")
            session.rollback()
        finally:
            session.close()
            return success

    #### Removal ####
    def remove_chatid(self, chatid):
        session = self.Session()
        log.info("chatid: {0} [{1}]".format(int(chatid), type(chatid)))
        c = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        try:
            log.info("deleting {0}".format(c))
            session.delete(c)
            session.commit()
        except:
            log.error("Delete error")
            session.rollback()
            print traceback.format_exc()
        finally:
            session.close()

    def remove_filter(self, chatid, name):
        session = self.Session()
        c = session.query(ChatID).filter_by(chatid=int(chatid)).first()

        for f in c.filters:
            if f.name == name:
                try:
                    session.delete(f)
                    session.commit()
                except:
                    log.error("Delete error")
                    session.rollback()

    def remove_location(self, chatid, name):
        session = self.Session()
        c = session.query(ChatID).filter_by(chatid=chatid).first()

        for f in c.locations:
            if f.name == name:
                try:
                    session.delete(f)
                    session.commit()
                except:
                    log.error("Delete error")
                    session.rollback()

    def remove_speciallocation(self, name):
        session = self.Session()
        c = session.query(SpecialLocation).filter_by(name=name).first()

        try:
            session.delete(c)
            session.commit()
        except:
            log.error("Delete error")
            session.rollback()

    def remove_fav(self, chatid, name):
        session = self.Session()
        c = session.query(ChatID).filter_by(chatid=chatid).first()

        for f in c.favs:
            if f.name == name:
                try:
                    session.delete(f)
                    session.commit()
                except:
                    log.error("Delete error")
                    session.rollback()

    def check_history(self, chatid, name, lat, lng, expiretime):
        session = self.Session()
        c = session.query(ChatID).filter_by(chatid=int(chatid)).first()
        success = False
        if c == None:
            return False
        try:
            for f in c.history:
                if f.name == name and float(f.lat) == float(lat) and float(f.lng) == float(lng) and f.expire == expiretime:
                    success = True
                    break

        except SQLAlchemyError as e:
            log.error("Error in adding chatid: {0}".format(e))
            session.rollback()

        finally:
            session.close()

        return success

    def check_speciallocation(self, minlat, maxlat, minlng, maxlng):
        session = self.Session()
        sps = session.query(SpecialLocation)

        for row in sps:
            if row.minlat == float(minlat) and row.maxlat == float(maxlat) and row.minlng == float(minlng) and row.maxlng == float(maxlng):
                return row.name

        return False

    def add_chatid(self, chatid, lat, lng, filters=[], locations={}, favs=[]):
        session = self.Session()
        chatid = ChatID(chatid=chatid, lat=lat, lng=lng)
        session.add(chatid)

        success = False

        try:
            session.commit()
            success = True
        except SQLAlchemyError as e:
            log.error("Error in adding chatid: {0}".format(e))
            session.rollback()
        finally:
            session.close()
            return success

    def add_history(self, chatid, name, lat, lng, expiretime):
        session = self.Session()
        success = False
        try:
            c = session.query(ChatID).filter_by(chatid=chatid).first()
            h = self._get_or_create(session, History, name=name, lat=lat, lng=lng, expire=expiretime)

            print c
            print h
            c.history.append(h)
            log.info("Adding {0}, {1}, {2}, {3}".format(name, lat, lng, expiretime))
            session.commit()
            success = True
        except SQLAlchemyError as e:
            log.debug("Error querying sample".format(e))
            session.rollback()
        except:
            print traceback.format_exc()
        finally:
            session.close()
            return success

    def add_location(self, chatid, name, lat, lng):
        session = self.Session()
        success = False
        try:
            chatid = session.query(ChatID).filter_by(chatid=chatid).first()
            location = self._get_or_create(session, Location, name=name, lat=lat, lng=lng)
            chatid.locations.append(location)
            session.commit()
            success = True
        except SQLAlchemyError as e:
            log.debug("Error querying sample".format(e))
            session.rollback()
        finally:
            session.close()
            return success

    def add_speciallocation(self, name, minlat, maxlat, minlng, maxlng):
        session = self.Session()
        success = False
        try:
            session = self.Session()
            sp = SpecialLocation(name=name, minlat=minlat, maxlat=maxlat, minlng=minlng,maxlng=maxlng)
            session.add(sp)
            session.commit()
            success = True
        except SQLAlchemyError as e:
            log.debug("Error querying sample".format(e))
            session.rollback()
        finally:
            session.close()
            return success

    def add_filter(self, chatid, name):
        session = self.Session()
        success = False
        try:
            chatid = session.query(ChatID).filter_by(chatid=str(chatid)).first()
            f = self._get_or_create(session, Filter, name=name)
            chatid.filters.append(f)
            session.commit()
            success = True
        except SQLAlchemyError as e:
            log.debug("Error querying sample".format(e))
            session.rollback()
        finally:
            session.close()
            return success

    def add_fav(self, chatid, name):
        session = self.Session()
        success = False
        try:
            chatid = session.query(ChatID).filter_by(chatid=str(chatid)).first()
            f = self._get_or_create(session, Fav, name=name)
            chatid.favs.append(f)
            session.commit()
            success = True
        except SQLAlchemyError as e:
            log.debug("Error querying sample".format(e))
            session.rollback()
        finally:
            session.close()
            return success
