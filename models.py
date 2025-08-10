import datetime as dt
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.db import Base

class CS2Server(Base):
    __tablename__ = "cs2_servers"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # 'surf' | 'bhop'
    host: Mapped[str] = mapped_column(String(64))
    port: Mapped[int] = mapped_column(Integer)
    rcon_host: Mapped[str] = mapped_column(String(64))
    rcon_port: Mapped[int] = mapped_column(Integer)
    # we do NOT store rcon_pass by default; keep in env. If you want, add a column.
    server_pass: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    status: Mapped[list["CS2Status"]] = relationship(back_populates="server")

class CS2Status(Base):
    __tablename__ = "cs2_status"
    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("cs2_servers.id", ondelete="CASCADE"))
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    map_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    players: Mapped[int] = mapped_column(Integer, default=0)
    max_players: Mapped[int] = mapped_column(Integer, default=0)

    server: Mapped[CS2Server] = relationship(back_populates="status")

class MapRequest(Base):
    __tablename__ = "cs2_map_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    server_key: Mapped[str] = mapped_column(String(16), index=True)
    map_name: Mapped[str] = mapped_column(String(64))
    requester_discord_id: Mapped[int] = mapped_column(BigInteger, index=True)
    thread_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="open")  # open/handled/rejected
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

class HelpTicket(Base):
    __tablename__ = "cs2_help_tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    server_key: Mapped[str] = mapped_column(String(16), index=True)
    opener_discord_id: Mapped[int] = mapped_column(BigInteger, index=True)
    thread_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    state: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("server_key", "opener_discord_id", "state", name="uq_open_ticket_per_user", sqlite_on_conflict="IGNORE"),
    )

class CS2PanelMessage(Base):
    __tablename__ = "cs2_panel_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    __table_args__ = (
        UniqueConstraint("channel_id", name="uq_panel_per_channel"),
    )
