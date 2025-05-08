

create table if not exists identity (
    id integer primary key autoincrement,
    rnsHash text not null,
    lxmfHash text not null,
    name text default "Anonymous-Goof #",
    username text unique not null,
    knownOn datetime default CURRENT_TIMESTAMP
);

create table if not exists msg_sent (
    msgID integer primary key autoincrement,
    receiverHash text not null,
    content text not null,
    time datetime default CURRENT_TIMESTAMP,
    align integer default 1,
    foreign key (receiverHash) references identity(rnsHash) on update cascade on delete set null
);

create table if not exists msg_recv (
    msgID integer primary key autoincrement,
    senderHash text not null,
    content text not null,
    time datetime default CURRENT_TIMESTAMP,
    align integer default 2,
    foreign key (senderHash) references identity(rnsHash) on update cascade on delete set null
);


create table if not exists vm_sent (
    vmID integer primary key autoincrement,
    receiverHash text not null,
    wavpath text not null,
    time datetime default CURRENT_TIMESTAMP,
    foreign key (receiverHash) references identity(rnsHash) on update cascade on delete set null
);

create table if not exists vm_recv (
    vmID integer primary key autoincrement,
    senderHash text not null,
    wavpath text not null,
    unread integer default 1,
    time datetime default CURRENT_TIMESTAMP,
    foreign key (senderHash) references identity(rnsHash) on update cascade on delete set null
);


create table if not exists file_sent (
    fileID integer primary key autoincrement,
    receiverHash text not null,
    filepath text not null,
    time datetime default CURRENT_TIMESTAMP,
    foreign key (receiverHash) references identity(rnsHash) on update cascade on delete set null
);

create table if not exists file_recv (
    fileID integer primary key autoincrement,
    senderHash text not null,
    filepath text not null,
    time datetime default CURRENT_TIMESTAMP,
    foreign key (senderHash) references identity(rnsHash) on update cascade on delete set null
);

