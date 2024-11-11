from flask import render_template, request, redirect, url_for, session, flash, make_response
from flask_login import login_user, logout_user, current_user, login_required, UserMixin
from forms import SignUpForm, RoomForm
from sqlalchemy.orm import selectinload, joinedload, aliased
from sqlalchemy import LABEL_STYLE_TABLENAME_PLUS_COL, LABEL_STYLE_DISAMBIGUATE_ONLY, desc

from models import *


def register_routes(app, db, bcrypt):
    
    @app.route('/')
    def home():
        subq = db.select(User).subquery()
        
        user_subq = aliased(User, subq, name="user")
        
        rooms = db.session.execute(
            db.select(Room, user_subq)
            .join(user_subq)
        )
        
        rooms_count = db.session.execute(
            func.count(Room.id)
        ).scalar()
        
        room_messages = db.session.execute(
            db.select(Message)
            .order_by(Message.id.desc())
            .join(Room)
        ).scalars()
        
        users = User.query.all()
        
        return render_template('home.html', rooms=rooms, users=users, rooms_count=rooms_count, room_messages=room_messages)
    
    @app.route('/signup', methods=['GET','POST'])
    def signup():
        form = SignUpForm()
        if request.method == 'GET':
            return render_template('signup.html', form=form)
        elif request.method == 'POST':
            username = request.form.get("username")
            password = request.form.get("password")
            email = request.form.get("email")
            
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

            user = User(name=username, password=hashed_password, email=email)
            
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('home'))
            
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return render_template('login.html')
        elif request.method == 'POST':
            username = request.form.get("username")
            password = request.form.get("password")
            
            user = User.query.filter(User.name==username).first()
            
            if bcrypt.check_password_hash(user.password, password):
                login_user(user)
                session['username'] = username
                flash("You've successfully logged in!")
                return redirect(url_for('home'))
            else:
                return 'Login Failed'
            
    @app.route('/logout')
    def logout():
        logout_user()
        session.clear()
        return redirect(url_for('home'))
    
    @app.route('/room/<int:id>', methods=['POST','GET'])
    def room(id):
        room = db.session.query(Room).get(id)
        room_messages = db.session.query(Message).filter(Message.room_id==id).join(User).all()
        participants = db.session.execute(
                db.select(Room)
                .filter(Room.id==room.id)
                .options(selectinload(Room.participants))
            ).scalar_one()
        print(participants)

        if request.method == 'POST':
            body = request.form.get('body')
            username = session["username"]
            message = Message(
                user_id=current_user.id,
                room_id=room.id,
                body=body
            )
            
            current_room = db.session.execute(
                db.select(Room)
                .filter(Room.id==room.id)
                .options(selectinload(Room.participants))
            ).scalar_one()
            
            new_participant = db.session.execute(
                db.select(User)
                .filter(User.id==current_user.id)
            ).scalar_one()
            
            if new_participant not in current_room.participants:
                current_room.participants.append(new_participant)
            
            user_to_add_message = db.session.execute(
                db.select(User)
                .filter(User.id==current_user.id)
                .options(joinedload(User.user_messages))
            ).unique().scalar_one()
            
            
            user_to_add_message.user_messages.append(message)
            
            db.session.add(message)
            db.session.commit()
            
           
            return redirect(url_for('room', id=room.id))
        
        return render_template('room.html',
                               room=room,
                               room_messages=room_messages,
                               participants=participants)
    
    @login_required
    @app.route('/create-room', methods=['POST', 'GET'])
    def createRoom():
        form = RoomForm()
        if request.method == 'POST':
            topic_name = request.form.get('topic')
            room_name = request.form.get('name')
            room_description = request.form.get('description')

            room = Room(
                    host_id=current_user.id,
                    topic = topic_name,
                    name=room_name,
                    description = room_description
                )
            
            db.session.add(room)
            db.session.commit()
            
            last_created_room_id = room.id
            
            current_room = db.session.execute(
                db.select(Room)
                .filter(Room.id==last_created_room_id)
                .options(selectinload(Room.participants))
            ).scalar_one()
            
            new_participant = db.session.execute(
                db.select(User)
                .filter(User.id==current_user.id)
            ).scalar_one()
            
            if new_participant not in current_room.participants:
                current_room.participants.append(new_participant)
                
            db.session.commit()
            
            return redirect(url_for('home'))
    
        return render_template('room_form.html', form=form)
            
            
    @login_required
    @app.route('/delete-message/<int:id>', methods=['POST', 'GET'])
    def deleteMessage(id):
        message = db.get_or_404(Message, id)
        
        if request.method == 'POST':
            db.session.delete(message)
            db.session.commit()
            return redirect(url_for('home'))
        
        return render_template('delete.html', obj=message)
    
    
    @login_required
    @app.route('/delete-room/<int:id>', methods=['POST', 'GET'])
    def deleteRoom(id):
        
        room = db.get_or_404(Room, id)
        
        if current_user.id != room.host_id:
            response = make_response("<h1>You're not allowed here!<h1>", 201)
            return response
        
        
        if request.method == 'POST':
            db.session.delete(room)
            db.session.commit()
            return redirect(url_for('home'))
        
        return render_template('delete.html', obj=room)
        
                        
    @app.template_filter('timesince')
    def timesince(time=False):
        
        now = datetime.now()
        if type(time) is int:
            diff = now - datetime.fromtimestamp(time)
        elif isinstance(time, datetime):
            diff = now - time
        elif not time:
            diff = 0
        second_diff = diff.seconds
        day_diff = diff.days

        if day_diff < 0:
            return ''

        if day_diff == 0:
            if second_diff < 10:
                return "just now"
            if second_diff < 60:
                return str(second_diff) + " seconds ago"
            if second_diff < 120:
                return "a minute ago"
            if second_diff < 3600:
                return str(second_diff // 60) + " minutes ago"
            if second_diff < 7200:
                return "an hour ago"
            if second_diff < 86400:
                return str(second_diff // 3600) + " hours ago"
        if day_diff == 1:
            return "Yesterday"
        if day_diff < 7:
            return str(day_diff) + " days ago"
        if day_diff < 31:
            return str(day_diff // 7) + " weeks ago"
        if day_diff < 365:
            return str(day_diff // 30) + " months ago"
        return str(day_diff // 365) + " years ago"
    
            