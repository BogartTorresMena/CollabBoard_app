from flask import Flask,render_template,request,redirect,url_for,session
import pymysql
from flask_babel import Babel,gettext as _
from datetime import timedelta

app=Flask(__name__)
app.secret_key ='020112897/app'
app.permanent_session_lifetime=timedelta(hours=12)

app.config['BABEL_DEFAULT_LOCALE']='en'
app.config['BABEL_SUPPORTED_LOCALES']=['es','en']
app.config['BABEL_TRANSLATION_DIRECTORIES']='translations'
def get_locale():
    return request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])
babel=Babel(app,locale_selector=get_locale)

key='020112897'
h='localhost'
u='Bogart'
p='020112897/sql'

def get_connection():
    return pymysql.connect(host=h,user=u,password=p,db='CollabBoard',cursorclass=pymysql.cursors.DictCursor)

def valAccess(b_id,u_id,adm=False):#Validar que el usuario activo tiene permiso de ver un tablero
    try:                           #(False=acceder,True=bloquear)
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                SELECT id_tablero,id_usuario,acceso
                FROM tableros
                WHERE id_tablero=%s
            """,(b_id))#Tablero al que se quiere acceder
            board=cursor.fetchone()
            if not board:
                return True #No existe
            if board['id_usuario']==u_id:
                return False #Usuario es admin
            if not adm:
                if board['acceso']=='pu':
                    return False #Tablero publico
                if board['acceso']=='a':
                    amigos=getFriends(board['id_usuario'])
                    for a in amigos:
                        if a['id']==u_id:
                            return False #Acceso de amigo
            return True
    except Exception as e:
        print(f"Error on validation: {e}")
        return True
    finally:
        con.close()

def getFriends(u_id):
    try:
        con = get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM amigos
                WHERE (id_in=%s or id_out=%s) AND estado='a'
            """,(u_id,u_id))#Todas las solisitudes aceptadas de/para el usuario
            friends=cursor.fetchall()#(solicitudes aceptadas representan amigos)
            for f in friends:
                f_id=f['id_in'] if f['id_in']!=u_id else f['id_out']
                cursor.execute("""
                    SELECT nombre FROM usuarios
                    WHERE id_usuario=%s
                """,(f_id))#Nombre de cada amigo
                f['name']=cursor.fetchone()['nombre']
                f['id']=f_id
    except Exception as e:
        return f"Error loading friends: {e}"
    finally:
        con.close()
    return friends

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        na=request.form['name']
        em=request.form['email']
        pa=request.form['password']
        try:
            con=get_connection()
            with con.cursor() as cursor:
                cursor.execute("SET @key=%s;",key)
                cursor.execute("""
                    INSERT INTO usuarios(
                        nombre,correo,contrasena
                    )VALUES(%s,%s,
                    AES_ENCRYPT(%s,@key));
                """,(na,em,pa))#Registrar usuario
                con.commit()
            return redirect(url_for('home'))
        except Exception as e:
            return f"Error on registration: {e}"
        finally:
            con.close()
    return render_template('register.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if 'u_id' in session:
        return redirect(url_for('home'))
    error=None
    if request.method=='POST':
        em=request.form['email']
        pa=request.form['password']
        try:
            con=get_connection()
            with con.cursor() as cursor:
                cursor.execute("SET @key=%s;",key)
                cursor.execute("""
                    SELECT id_usuario,nombre FROM usuarios
                    WHERE correo=%s AND
                    contrasena=AES_ENCRYPT(%s,@key)
                """,(em,pa))#Validar correo y contraseña
                user=cursor.fetchone()
                if user:
                    session['u_id']=user['id_usuario']
                    session['u_name']=user['nombre']
                    session.permanent=True
                    return redirect(url_for('home'))
                else:
                    error=1
        except Exception as e:
            return f"Error on login: {e}"
        finally:
            con.close()
    return render_template('login.html',error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/new_board',methods=['GET','POST'])
def new_board():
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if request.method=='POST':
        ti=request.form['title']
        de=request.form['desc']
        n=int(request.form.get('num_listas',3))
        acc=request.form['modo']
        try:
            con=get_connection()
            with con.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO tableros(
                        titulo,descripcion,id_usuario,acceso
                    )VALUES(%s,%s,%s,%s)
                """,(ti,de,session['u_id'],acc))#Registrar tablero
                con.commit()
                cursor.execute("SELECT LAST_INSERT_ID() AS id")
                b_id=cursor.fetchone()['id']
                for i in range(n):
                    cursor.execute("""
                        INSERT INTO listas(titulo,id_tablero,orden)
                        VALUES(%s,%s,%s)
                    """,(f'L{i+1}',b_id,i+1))#Registrar listas por defecto (1 a 10)
                con.commit()
            return redirect(url_for('boards'))
        except Exception as e:
            return f"Error on new board: {e}"
        finally:
            con.close()
    return render_template('new_board.html')

@app.route('/boards',methods=['GET','POST'])
def boards():
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if request.method=='POST':
        try:
            b_id=int(request.form['id_tablero'])
            acc=request.form['modo']
            con=get_connection()
            with con.cursor() as cursor:
                cursor.execute("""
                    UPDATE tableros SET acceso=%s
                    WHERE id_tablero=%s AND id_usuario=%s
                """,(acc,b_id,session['u_id']))#Cambiar acceso del
                con.commit()
        except Exception as e:
            return f"Error on sharing: {e}"
        finally:
            con.close()
        return redirect(url_for('boards'))
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                SELECT *
                FROM tableros WHERE id_usuario=%s
                ORDER BY fecha_creacion DESC
            """,(session['u_id']))#Lista de tableros del usuario activo
            u_boards=cursor.fetchall()
    except Exception as e:
        return f"Error on boards load: {e}"
    finally:
        con.close()
    return render_template('boards.html',u_boards=u_boards)

@app.route('/board/<int:b_id>')
def board(b_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("Tablero no existe o no estas autorizado")
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                SELECT id_tablero,titulo,descripcion
                FROM tableros
                WHERE id_tablero=%s;
            """,(b_id))#Datos del tablero
            board=cursor.fetchone()
            cursor.execute("""
                SELECT id_lista,titulo,orden
                FROM listas
                WHERE id_tablero=%s
                ORDER BY orden
            """,(b_id))#Listas del tablero
            lists=cursor.fetchall()
            for l in lists:
                cursor.execute("""
                    SELECT id_tarjeta,titulo,descripcion,
                    fecha_creacion,fecha_vencimiento
                    FROM tarjetas
                    WHERE id_lista=%s
                    ORDER BY fecha_creacion
                """,(l['id_lista']))#Todas las targetas de cada lista
                l['cards']=cursor.fetchall()
    except Exception as e:
        return f"Error al cargar tablero: {e}"
    finally:
        con.close()
    et=_("¿Eliminar este tablero? No se puede deshacer")
    return render_template('board.html',board=board,lists=lists,et=et)

@app.route('/board/<int:b_id>/rename',methods=['POST'])
def rename(b_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id'],True):
        return _("No autorizado")
    ti=request.form['nuevo_ti']
    try:
        con = get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                UPDATE tableros SET titulo=%s
                WHERE id_tablero=%s
            """,(ti,b_id))#Renombrar tablero
            con.commit()
    except Exception as e:
        return f"Error renombrando lista: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/delete_board/<int:b_id>',methods=['POST'])
def delete_board(b_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id'],True):
        return _("Tablero no existe o no estas autorizado")
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                DELETE FROM tableros
                WHERE id_tablero=%s
            """,(b_id))#Eliminar un tablero (ON DELETE CASCADE)
            con.commit()
    except Exception as e:
        return f"Error on board delete: {e}"
    finally:
        con.close()
    return redirect(url_for('boards'))

@app.route('/board/<int:b_id>/add_list')
def add_list(b_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("No autorizado")
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM listas WHERE id_tablero=%s",(b_id))
            count=cursor.fetchone()['total']+1
            if 10<count:
                return "Too many lists"
            na=f"L{count}"
            cursor.execute("""
                INSERT INTO listas(
                    titulo,id_tablero,orden
                )VALUES(%s,%s,%s)
            """,(na,b_id,count))#Registrar lista nueva para un tablero
            con.commit()
    except Exception as e:
        return f"Error adding list: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/board/<int:b_id>/rename_list/<int:l_id>',methods=['POST'])
def rename_list(b_id,l_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("No autorizado")
    ti=request.form['nuevo_ti']
    try:
        con = get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                UPDATE listas SET titulo=%s
                WHERE id_lista=%s
            """,(ti,l_id))#Renombrar lista
            con.commit()
    except Exception as e:
        return f"Error renombrando lista: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/board/<int:b_id>/delete_list/<int:l_id>')
def delete_list(b_id,l_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("No autorizado")
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                DELETE FROM listas
                WHERE id_lista = %s
            """,(l_id))#Eliminar lista (ON DELETE CASCADE)
            cursor.execute("""
                SELECT id_lista FROM listas
                WHERE id_tablero=%s
                ORDER BY orden
            """,(b_id))#Guradar id del resto de las listas
            ls=cursor.fetchall()
            for idx,l in enumerate(ls,start=1):
                cursor.execute("""
                    UPDATE listas
                    SET orden=%s
                    WHERE id_lista=%s
                """,(idx,l['id_lista']))#Reasignar el orden de las listas
            con.commit()
    except Exception as e:
        return f"Error deliting list: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/board/<int:b_id>/add_card',methods=['POST'])
def add_card(b_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("No autorizado")
    l_id=request.form['id_lista']
    ti=request.form['titulo']
    de=request.form['desc']
    fv=request.form['fecha_v']
    if 'ncb' in request.form:
        fv=None
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tarjetas(
                    titulo,descripcion,id_lista,fecha_vencimiento
                )VALUES(%s,%s,%s,%s)
            """,(ti,de,l_id,fv))#Registrar nueva targeta
            con.commit()
    except Exception as e:
        return f"Error adding card: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/board/<int:b_id>/edit_card/<int:c_id>',methods=['POST'])
def edit_card(b_id,c_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("No autorizado")
    ti=request.form['titulo']
    de=request.form['desc']
    fv=request.form['fecha_v']
    if 'ncb' in request.form:
        fv=None
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                UPDATE tarjetas
                SET titulo=%s,
                    descripcion=%s,
                    fecha_vencimiento=%s
                WHERE id_tarjeta=%s
            """,(ti,de,fv,c_id))#Editar targeta
            con.commit()
    except Exception as e:
        return f"Error editing card: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/board/<int:b_id>/delete_card/<int:c_id>')
def delete_card(b_id,c_id):
    if 'u_id' not in session:
        return redirect(url_for('login'))
    if valAccess(b_id,session['u_id']):
        return _("No autorizado")
    try:
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                DELETE FROM tarjetas
                WHERE id_tarjeta=%s
            """,(c_id))#Eliminar una targeta
            con.commit()
    except Exception as e:
        return f"Error deliting card: {e}"
    finally:
        con.close()
    return redirect(url_for('board',b_id=b_id))

@app.route('/friends',methods=['GET','POST'])
def friends():
    if 'u_id' not in session:
        return redirect(url_for('login'))
    u_id = session['u_id']
    if request.method=='POST':
        ac=request.form.get('accion')
        t_id=int(request.form.get('target'))
        try:
            con=get_connection()
            with con.cursor() as cursor:
                if ac=='e':
                    cursor.execute("""
                        DELETE FROM amigos
                        WHERE (id_in=%s AND id_out=%s)
                           OR (id_in=%s AND id_out=%s)
                    """,(u_id,t_id,t_id,u_id))#Eliminar una solicitud
                else:
                    cursor.execute("""
                        UPDATE amigos
                        SET estado=%s
                        WHERE id_in=%s AND id_out=%s
                    """,(ac,u_id,t_id))#Aceptar o rechazar una solicitud
                con.commit()
        except Exception as e:
            return f"Error on friend requests: {e}"
        finally:
            con.close()
        return redirect(url_for('friends'))
    frs=getFriends(u_id)
    try:
        con = get_connection()
        with con.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM amigos
                WHERE id_in=%s AND estado='p'
            """,(u_id,))#Solocitudes pendientes recividas
            inbox=cursor.fetchall()
            for i in inbox:
                cursor.execute("""
                    SELECT nombre FROM usuarios
                    WHERE id_usuario=%s
                """,(i['id_out']))#Nombres de usuario que solicitan
                i['name']=cursor.fetchone()['nombre']
            cursor.execute("""
                SELECT * FROM amigos
                WHERE id_out=%s AND estado!='a'
            """,(u_id,))#Soliciyudes pendientes o ignoradas enviadas
            sent=cursor.fetchall()
            for s in sent:
                cursor.execute("""
                    SELECT nombre FROM usuarios
                    WHERE id_usuario=%s
                """,(s['id_in']))#Nombres de usuario a quien se envia
                s['name']=cursor.fetchone()['nombre']
    except Exception as e:
        return f"Error loading friends: {e}"
    finally:
        con.close()
    return render_template('friends.html',fr=frs,r_in=inbox,r_out=sent,u_id=u_id)

@app.route('/add_friend',methods=['POST'])
def add_friend():
    if 'u_id' not in session:
        return redirect(url_for('login'))
    u_id=session['u_id']
    try:
        n_id=int(request.form['n_amigo'])
        con=get_connection()
        with con.cursor() as cursor:
            cursor.execute("SELECT id_usuario FROM usuarios WHERE id_usuario=%s",(n_id))
            ex=cursor.fetchone()
            if not ex:
                session['error']=_("No hay usuario con esta ID")
            else:
                cursor.execute("""
                    SELECT * FROM amigos
                    WHERE(id_in=%s AND id_out=%s)
                    OR(id_in=%s AND id_out=%s)
                """,(u_id,n_id,n_id,u_id))#Registrar una solicitud
                ex=cursor.fetchone()
                if ex:
                    session['error']=_("Este usuario ya es tu amigo o tiene solicitud pendiente.")
                else:
                    cursor.execute("""
                        INSERT INTO amigos(id_out,id_in,estado)
                        VALUES(%s,%s,'p')
                    """,(u_id,n_id))
                    con.commit()
    except Exception as e:
        return f"Error on friend request: {e}"
    finally:
        con.close()
    return redirect(url_for('friends'))

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True,use_reloader=False)