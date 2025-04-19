# Пояснения к функциям
1. ssh_connect(hostname) - Устанавливает SSH-соединение с удалённым сервером
2. get_os_type(ssh_client) - Определяет тип ОС на удалённом сервере
3. get_load_average(ssh_client) - Получает среднюю загрузку CPU за 1 минуту
4. install_postgresql(ssh_client, os_type) - Устанавливает PostgreSQL
5. get_postgresql_conf_path(ssh_client) - Находит путь к postgresql.conf
6. get_pg_hba_path(ssh_client) - Находит путь к pg_hba.conf (файлу аутентификации)
7. configure_postgresql(ssh_client, os_type, other_server_ip) - Настраивает PostgreSQL для внешних подключений
8. create_user(ssh_client) - Создаёт пользователя student в PostgreSQL
9. test_db(ssh_client) - Проверяет работоспособность БД, выполняя тестовый запрос

# Пример запуска
python3 task.py 192.168.1.1,192.168.1.2

