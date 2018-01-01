# mmogamelab
MMOGameLab основан на движке metagam.
### metagam
Metagam is a software for providing MMO game engine as a service.

Copyright 2013, Alexander Lourier <aml@joyteam.ru>, Joy Team.

Metagam is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

Metagam is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

## Разворот конструктора

Для установки понадобится Denian Linux версии не ниже Squeeze 6.
Желательно использовать стабильную версию Jessie 8.
Работаем от root пользователя. Если у вас права юзера, используйте `sudo su`.

#### Свежие зависимости

Устанавливаем необходимые из свежих репозиториев пакеты:
```bash
apt update
apt install nano mc screen libwww-perl mysql-client mysql-server nginx sudo
```
Во время установки MySQL сервера будет предложено ввести пароль для root пользователя.
Введите пароль и запишите его. Он понадобится в конечных стадиях установки.

#### Репозитории

Редактируем файл со списком репозиториев
```bash
nano /etc/apt/sources.list
```
В предложенном списке надо поставить знак решётки (диез) `#` перед каждой строкой,содержащей некую сущность типа
```
deb <URL> jessie main contrib non-free
```
Подсветка Nano покажет, что строка закомментирована и больше не будет иметь смысл.
Далее необходимо дописать в конце файла с новой строки необходимые для работы репозитории. Их несколько:
```bash
deb http://deb.rulezz.ru/debian/ aml main
```
Это репозиторий aml. В нём есть большинство необходимых пакетов для разворота.
```bash
deb http://archive.debian.org/debian squeeze main contrib non-free
deb http://archive.debian.org/debian squeeze-lts main contrib non-free
```
Это архивные репозитории debian squeeze. Они нужны для удовлетворения низкоуровневых зависимостей.
Закрываем файл `sources.list` с помощью горячей клавиши **Ctrl+X** и подтверждением перезаписи файла клавишей **Y** и **Enter** последовательно.
Для архивных репозиториев нужно применить наше согласие на работу с устаревшими пакетами, которые могут быть нестабильны и подвергать наш сервер риску. Для этого откроем файл
```bash
nano /etc/apt/apt.conf
```
Обычно этот файл пуст. Просто записываем или дописываем в конец файла.
```bash
Acquire::Check-Valid-Until false;
```
Закрываем редактор, сохранив изменения. (**Ctrl+X**, **Y**, **Enter**)
Загружаем публичный ключ aml и применяем его для менеджера пакетов
```bash
wget http://aml.rulezz.ru/aml.pgp -O- | apt-key add -
```
Теперь мы готовы получить список пакетов для последующей установки
```bash
apt update
```
#### Удовлетворение зависимостей
Прежде чем загружать все пакеты, мы должны удовлетворить зависимость в паре пакетов, не входящих в установленные репозитории.
```bash
wget http://ftp.ru.debian.org/debian/pool/main/g/gcc-4.9/libgomp1_4.9.2-10_amd64.deb
dpkg -i libgomp1_4.9.2-10_amd64.deb
rm libgomp1_4.9.2-10_amd64.deb
apt purge python2.7 python2.7-minimal libjpeg62-turbo
rm /usr/bin/python
```

#### Установка пакетов
```bash
apt install memcached rsync psmisc python2.6 python-minimal concurrence python-template python-cassandra jsgettext gettext make python-imaging python-adns python-whois python-stemmer python-cssutils realpath cassandra realplexor stunnel pywhois
```
На все предупреждения ставим **Y**. Во время установки пакетов будут появляться диалоги. Везде выбираем **Ok** с помощью клавиши **Tab** и **Yes** с помощью стрелок.

#### Подготовка файлов конструктора
Склонируйте репозиторий конструктора (вы можете подставить значение чистого конструктора aml)
```bash
cd /home
git clone https://github.com/chronosms/mmogamelab.git
mv -R mmogamelab/ mg/
mkdir webdav
chmod -R 777 /home/webdav
chmod -R 777 /home/mg
mv -R /home/mg/etcmetagam /etc/metagam
cd /home/mg
make
mv start ~/start
mv reload ~/reload
cd ~
chmod +x start reload
```
### Настройка
Перед запуском стоит настроить пакеты для корректной работы конструктора
#### nginx
```bash
rm /etc/nginx/conf.d/default.conf
nano /etc/nginx/conf.d/default.conf
```
Вставляем в пустой файл конфигурации следующее содержимое
```conf
include "/etc/nginx/nginx-metagam.conf";
server {
	listen 0.0.0.0:80;
	server_name www.domain domain;
	charset off;
	root /home/mg/static;
	client_max_body_size 10m;
	location ~ ^/st/([0-9-]+/|) {
		root /home/mg/static/;
		rewrite ^/st/([0-9-]+/|)(.+)$ /$2 break;
		access_log /var/log/nginx/mmoconstructor-static.log combined;
		expires 3M;
	}
	location ~ ^/st-mg/([0-9-]+/|) {
		root /home/mg/static/;
		rewrite ^/st-mg/([0-9-]+/|)(.+)$ /$2 break;
		access_log /var/log/nginx/mmoconstructor-static.log combined;
		expires 3M;
	}
	location = /favicon.ico {
		root /home/mg/static/;
		access_log /var/log/nginx/mmoconstructor-static.log combined;
		expires 3M;
	}
	location /rpl {
		proxy_pass http://localhost:8088;
		proxy_read_timeout 200;
		access_log /var/log/nginx/mmoconstructor-realplexor.log combined;
	}
	location / {
		proxy_pass http://metagam;
		proxy_set_header X-Real-Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_read_timeout 200;
		access_log /var/log/nginx/mmoconstructor.log combined;
	}
}
server {
	listen 0.0.0.0:80;
	server_name storage.domain;
	client_max_body_size 20m;
	location / {
		root /home/webdav;
		client_body_temp_path /tmp;
		dav_methods PUT DELETE MKCOL COPY MOVE;
		create_full_put_path on;
		dav_access user:rw group:rw all:rw;
	}
}
```
В параметре `server_name` необходимо обязательно заменить ключевое слово `domain` на домен для вашего конструктора без `www` и `http://`. Там, где надо, уже прописано `www`. Если вы разворачиваете конструктор локально, укажите домен локальной зоны `.local`. Пример правильно заполненных параметров в трёх местах:
```conf
server_name www.mmogamelab.ru mmogamelab.ru;
server_name storage.mmogamelab.ru;
```
Так как мы используем усложнённую схему доменных имён, нужно увеличить размер hash_bucket.
```bash
nano /etc/nginx/nginx.conf
```
После открытия директивы:
```conf
http{
```
Поставьте в конце строки новую строку и под этой директивой напишите следующий параметр:
```conf
server_names_hash_bucket_size 64;
```
#### cassandra
```bash
nano /etc/cassandra/cassandra-env.sh
```
Приблизительно в конце файла, если прокрутить с помощью стрелок, можно найти короткую строку, где изложено следующее:
```sh
-Xss128k
```
Нужно заменить это содержимое на:
```sh
-Xss256k
```
После чего перезагрузить СУБД Cassandra:
```bash
service cassandra restart
```
#### realplexor
```bash
nano /etc/realplexor.conf
```
Меняем значения, выискивая с помощью стрелок
```conf
WAIT_TIMEOUT => 60
```
меняем на
```conf
WAIT_TIMEOUT => 20
```
#####-----
```conf
IN_TIMEOUT => 20
```
меняем на
```conf
IN_TIMEOUT => 10
```
#####-----
```conf
OFFLINE_TIMEOUT => 300
```
меняем на
```conf
OFFLINE_TIMEOUT => 30
```
Закрываем редактор с сохранением изменений.
#### metagam
```bash
nano /etc/metagam/metagam.conf
```
Необходимо указать свои значения в некоторых строках:
```conf
id: любое_ключевое_латинское_название
addr: IP_адрес_сервера
domain: домен_конструктора
```
Замените значения и сохраните изменения
#### Почта (exim4)
```bash
dpkg-reconfigure exim4-config
```
Если пакет не найден:
```bash
apt install exim4
```
После повторите предыдущий шаг.
Откроется много диалоговых окон. В первых окнах нужно указать категорию веб-сайт, чтобы сервер получил возможность посылать письма. В последующих наблюдать за значениями и там, где есть примеры доменов, указывать свой домен.
### Запуск конструктора
Так как сервисный режим работы никто ещё не придумал, и всем лень сделать конструктор в качестве демона, запустим конструктор через `screen`:
```bash
screen -R mg
```
Каждый раз, когда вам нужно будет обратиться в консоль конструктора, вы сможете это сделать с помощью этой команды.
Открыв консоль конструктора, выполните команду:
```bash
./start
```
После чего по домену, который вы выбрали для конструктора, можно будет увидеть главную страницу конструктора.
### Доступ к исходному коду
Подключитесь к конструктору по протоколу SFTP или посмотрите гайды по развороту FTP сервера. Используйте данные root пользователя для авторизации. В качестве базового каталога, который будет служить корневым для подключения, укажите `/home/mg`.
Как разработчик, я предпочитаю налаживать подключение через редактор кода Atom с установленным плагином remote-ftp, но для рядовых пользователей рекомендую загрузить FileZilla и Notepad++, большего вам не нужно.
### Получение админки
Для начала нам нужно включить обходные пути, изменив пару условий в реальном конструкторе. Откройте файл
```bash
mg/core/auth.py
```
Найдите с помощью поиска Notepad++ следующую ключевую фразу:
```python
elif user.get("inactive"):
```
Добавьте **not**, чтобы получилась следующая строка:
```python
elif not user.get("inactive"):
```
Для получения привилегий администратора также замените эту строку
```python
if user_id == self.clconf("admin_user"):
```
...на строку с обратным логическим значением
```python
if user_id != self.clconf("admin_user"):
```
Сохраните код и загрузите правки на сервер. Подключитесь к серверу по SSH и перезагрузите конструктор командой
```bash
./reload
```
Далее можно зарегистрироваться на конструкторе. Щёлкните на ссылку **register** и пройдите нетрудную процедуру регистрации. После регистрации появится ошибка **500 Internal Server Error**. Игнорируя ошибку, перейдите на главную страницу конструктора и, щёлкнув по ссылке **log in**, войдите под своими регистрационными данными, как ни в чём не бывало. В кабинете вас ждёт элемент **Constructor administration**. Кликнув по ссылке, вы попадёте в админку конструктора. Перейдите в раздел **Cluster**, вкладку **Cluster configuration**.
В поле **Storage servers** запишите `storage.domain`, где **domain** - доменное имя конструктора без **www** и  **http://**
**MySQL database name** - `metagam`
**MySQL user name** - `root`
**MySQL user password** - пароль от сервера MySQL
**Server locale** - `ru`
Остальные поля редактированию не подлежат. Редактируйте только тогда, когда действительно уверены в том, что вы делаете. Нажимайте кнопку **Save**.
Обновите страницу админки. Перейдите по ссылке **Моё досье**. Перейдите по ссылке **Привилегии**. Проставьте последовательно все галочки (да, их много) и нажмите **Сохранить**.
Вернитесь к правке файла `mg/core/auth.py` и проведите обратные операции.
Конструктор успешно русифицирован и настроен. Осталось сгенерировать базу данных.
#### Генерация БД MySQL
Откройте терминал сервера, введите команду
```bash
mysql -p
```
Введите пароль от сервера MySQL. Откроется строка управления. В ней выполните запрос
```sql
CREATE DATABASE metagam;
```
После выполнения команды закройте строку с помощью **Ctrl+D**.
Далее необходимо perl скриптом сгенерировать таблицы в БД MySQL:
```bash
export PYTHONPATH=/home/mg
cd /home/mg/perl
./restructure.pl
```
По последним изменениям необходимо перезагрузить конструктор
```bash
cd ~
./reload
```
