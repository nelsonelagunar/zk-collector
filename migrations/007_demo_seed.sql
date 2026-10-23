-- Demo seed data (MYK-377): >=100 colaboradores + empresa/dispositivos/usuarios demo.
-- Idempotente: guarda por llave natural (employee_code/username UNIQUE, links PK,
-- devices por address). Usuarios demo usan la contrasena 'demo1234' (Argon2id).

-- Empresa (config)
INSERT OR IGNORE INTO system_config (key, value, description) VALUES
    ('company_name', 'Empresa Demo S.A. de C.V.', 'Nombre de la empresa (datos demo)'),
    ('demo_seed_version', '1', 'Version del seed de datos demo (MYK-377)');

-- Colaboradores demo (120)
INSERT OR IGNORE INTO employees
    (employee_code, first_name, last_name, email, phone, department, position,
     hire_date, status, notes)
VALUES
    ('EMP-0001', 'Jose', 'Garcia Gonzalez', 'jose.garcia01@demo-corp.com', '55-0000-0001', 'Tecnologia', 'Desarrollador Backend', '2018-01-01', 'active', 'Registro demo MYK-377'),
    ('EMP-0002', 'Maria', 'Martinez Gomez', 'maria.martinez02@demo-corp.com', '55-0000-0002', 'Recursos Humanos', 'Especialista RH', '2019-06-12', 'active', 'Registro demo MYK-377'),
    ('EMP-0003', 'Juan', 'Lopez Mendoza', 'juan.lopez03@demo-corp.com', '55-0000-0003', 'Finanzas', 'Contador', '2020-11-23', 'active', 'Registro demo MYK-377'),
    ('EMP-0004', 'Ana', 'Gonzalez Vargas', 'ana.gonzalez04@demo-corp.com', '55-0000-0004', 'Operaciones', 'Coordinador de Operaciones', '2021-04-07', 'active', 'Registro demo MYK-377'),
    ('EMP-0005', 'Luis', 'Perez Martinez', 'luis.perez05@demo-corp.com', '55-0000-0005', 'Ventas', 'Ejecutivo de Ventas', '2022-09-18', 'active', 'Registro demo MYK-377'),
    ('EMP-0006', 'Laura', 'Sanchez Flores', 'laura.sanchez06@demo-corp.com', '55-0000-0006', 'Mercadotecnia', 'Especialista en Marketing', '2023-02-02', 'active', 'Registro demo MYK-377'),
    ('EMP-0007', 'Carlos', 'Ramirez Chavez', 'carlos.ramirez07@demo-corp.com', '55-0000-0007', 'Soporte', 'Tecnico de Soporte N1', '2024-07-13', 'active', 'Registro demo MYK-377'),
    ('EMP-0008', 'Sofia', 'Torres Medina', 'sofia.torres08@demo-corp.com', '55-0000-0008', 'Administracion', 'Asistente Administrativo', '2025-12-24', 'active', 'Registro demo MYK-377'),
    ('EMP-0009', 'Miguel', 'Flores Ibarra', 'miguel.flores09@demo-corp.com', '55-0000-0009', 'Logistica', 'Coordinador de Almacen', '2018-05-08', 'active', 'Registro demo MYK-377'),
    ('EMP-0010', 'Elena', 'Rivera Ramirez', 'elena.rivera10@demo-corp.com', '55-0000-0010', 'Produccion', 'Operador', '2019-10-19', 'active', 'Registro demo MYK-377'),
    ('EMP-0011', 'Jorge', 'Gomez Cruz', 'jorge.gomez11@demo-corp.com', '55-0000-0011', 'Tecnologia', 'Desarrollador Frontend', '2020-03-03', 'active', 'Registro demo MYK-377'),
    ('EMP-0012', 'Patricia', 'Diaz Moreno', 'patricia.diaz12@demo-corp.com', '55-0000-0012', 'Recursos Humanos', 'Reclutador', '2021-08-14', 'active', 'Registro demo MYK-377'),
    ('EMP-0013', 'Ricardo', 'Reyes Romero', 'ricardo.reyes13@demo-corp.com', '55-0000-0013', 'Finanzas', 'Analista Financiero', '2022-01-25', 'active', 'Registro demo MYK-377'),
    ('EMP-0014', 'Claudia', 'Cruz Perez', 'claudia.cruz14@demo-corp.com', '55-0000-0014', 'Operaciones', 'Supervisor de Planta', '2023-06-09', 'active', 'Registro demo MYK-377'),
    ('EMP-0015', 'Fernando', 'Gutierrez Diaz', 'fernando.gutierrez15@demo-corp.com', '55-0000-0015', 'Ventas', 'Gerente de Cuenta', '2024-11-20', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0016', 'Lucia', 'Chavez Rojas', 'lucia.chavez16@demo-corp.com', '55-0000-0016', 'Mercadotecnia', 'Disenador Grafico', '2025-04-04', 'active', 'Registro demo MYK-377'),
    ('EMP-0017', 'Alejandro', 'Vasquez Castillo', 'alejandro.vasquez17@demo-corp.com', '55-0000-0017', 'Soporte', 'Tecnico de Soporte N2', '2018-09-15', 'active', 'Registro demo MYK-377'),
    ('EMP-0018', 'Marta', 'Mendoza Lopez', 'marta.mendoza18@demo-corp.com', '55-0000-0018', 'Administracion', 'Recepcionista', '2019-02-26', 'active', 'Registro demo MYK-377'),
    ('EMP-0019', 'Francisco', 'Rojas Rivera', 'francisco.rojas19@demo-corp.com', '55-0000-0019', 'Logistica', 'Chofer', '2020-07-10', 'active', 'Registro demo MYK-377'),
    ('EMP-0020', 'Carmen', 'Jimenez Vasquez', 'carmen.jimenez20@demo-corp.com', '55-0000-0020', 'Produccion', 'Supervisor de Linea', '2021-12-21', 'active', 'Registro demo MYK-377'),
    ('EMP-0021', 'Diego', 'Moreno Aguilar', 'diego.moreno21@demo-corp.com', '55-0000-0021', 'Tecnologia', 'Ingeniero DevOps', '2022-05-05', 'active', 'Registro demo MYK-377'),
    ('EMP-0022', 'Sandra', 'Herrera Garcia', 'sandra.herrera22@demo-corp.com', '55-0000-0022', 'Recursos Humanos', 'Analista de Nomina', '2023-10-16', 'active', 'Registro demo MYK-377'),
    ('EMP-0023', 'Pablo', 'Medina Torres', 'pablo.medina23@demo-corp.com', '55-0000-0023', 'Finanzas', 'Tesorero', '2024-03-27', 'active', 'Registro demo MYK-377'),
    ('EMP-0024', 'Paula', 'Aguilar Gutierrez', 'paula.aguilar24@demo-corp.com', '55-0000-0024', 'Operaciones', 'Planificador', '2025-08-11', 'active', 'Registro demo MYK-377'),
    ('EMP-0025', 'Andres', 'Vargas Herrera', 'andres.vargas25@demo-corp.com', '55-0000-0025', 'Ventas', 'Vendedor de Campo', '2018-01-22', 'active', 'Registro demo MYK-377'),
    ('EMP-0026', 'Silvia', 'Castillo Solis', 'silvia.castillo26@demo-corp.com', '55-0000-0026', 'Mercadotecnia', 'Content Manager', '2019-06-06', 'active', 'Registro demo MYK-377'),
    ('EMP-0027', 'Javier', 'Navarro Sanchez', 'javier.navarro27@demo-corp.com', '55-0000-0027', 'Soporte', 'Ingeniero de Soporte', '2020-11-17', 'active', 'Registro demo MYK-377'),
    ('EMP-0028', 'Rocio', 'Romero Reyes', 'rocio.romero28@demo-corp.com', '55-0000-0028', 'Administracion', 'Especialista en Compras', '2021-04-01', 'active', 'Registro demo MYK-377'),
    ('EMP-0029', 'Pedro', 'Solis Jimenez', 'pedro.solis29@demo-corp.com', '55-0000-0029', 'Logistica', 'Auxiliar de Envios', '2022-09-12', 'active', 'Registro demo MYK-377'),
    ('EMP-0030', 'Leticia', 'Ibarra Navarro', 'leticia.ibarra30@demo-corp.com', '55-0000-0030', 'Produccion', 'Tecnico de Mantenimiento', '2023-02-23', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0031', 'Raul', 'Garcia Gonzalez', 'raul.garcia31@demo-corp.com', '55-0000-0031', 'Tecnologia', 'Analista de Datos', '2024-07-07', 'active', 'Registro demo MYK-377'),
    ('EMP-0032', 'Gabriela', 'Martinez Gomez', 'gabriela.martinez32@demo-corp.com', '55-0000-0032', 'Recursos Humanos', 'Coordinador RH', '2025-12-18', 'active', 'Registro demo MYK-377'),
    ('EMP-0033', 'Sergio', 'Lopez Mendoza', 'sergio.lopez33@demo-corp.com', '55-0000-0033', 'Finanzas', 'Auditor Interno', '2018-05-02', 'active', 'Registro demo MYK-377'),
    ('EMP-0034', 'Adriana', 'Gonzalez Vargas', 'adriana.gonzalez34@demo-corp.com', '55-0000-0034', 'Operaciones', 'Coordinador de Operaciones', '2019-10-13', 'active', 'Registro demo MYK-377'),
    ('EMP-0035', 'Oscar', 'Perez Martinez', 'oscar.perez35@demo-corp.com', '55-0000-0035', 'Ventas', 'Ejecutivo de Ventas', '2020-03-24', 'active', 'Registro demo MYK-377'),
    ('EMP-0036', 'Monica', 'Sanchez Flores', 'monica.sanchez36@demo-corp.com', '55-0000-0036', 'Mercadotecnia', 'Especialista en Marketing', '2021-08-08', 'active', 'Registro demo MYK-377'),
    ('EMP-0037', 'Adrian', 'Ramirez Chavez', 'adrian.ramirez37@demo-corp.com', '55-0000-0037', 'Soporte', 'Tecnico de Soporte N1', '2022-01-19', 'active', 'Registro demo MYK-377'),
    ('EMP-0038', 'Veronica', 'Torres Medina', 'veronica.torres38@demo-corp.com', '55-0000-0038', 'Administracion', 'Asistente Administrativo', '2023-06-03', 'active', 'Registro demo MYK-377'),
    ('EMP-0039', 'Hector', 'Flores Ibarra', 'hector.flores39@demo-corp.com', '55-0000-0039', 'Logistica', 'Coordinador de Almacen', '2024-11-14', 'active', 'Registro demo MYK-377'),
    ('EMP-0040', 'Natalia', 'Rivera Ramirez', 'natalia.rivera40@demo-corp.com', '55-0000-0040', 'Produccion', 'Operador', '2025-04-25', 'active', 'Registro demo MYK-377'),
    ('EMP-0041', 'Jose', 'Gomez Cruz', 'jose.gomez41@demo-corp.com', '55-0000-0041', 'Tecnologia', 'Ingeniero QA', '2018-09-09', 'active', 'Registro demo MYK-377'),
    ('EMP-0042', 'Maria', 'Diaz Moreno', 'maria.diaz42@demo-corp.com', '55-0000-0042', 'Recursos Humanos', 'Especialista RH', '2019-02-20', 'active', 'Registro demo MYK-377'),
    ('EMP-0043', 'Juan', 'Reyes Romero', 'juan.reyes43@demo-corp.com', '55-0000-0043', 'Finanzas', 'Contador', '2020-07-04', 'active', 'Registro demo MYK-377'),
    ('EMP-0044', 'Ana', 'Cruz Perez', 'ana.cruz44@demo-corp.com', '55-0000-0044', 'Operaciones', 'Supervisor de Planta', '2021-12-15', 'active', 'Registro demo MYK-377'),
    ('EMP-0045', 'Luis', 'Gutierrez Diaz', 'luis.gutierrez45@demo-corp.com', '55-0000-0045', 'Ventas', 'Gerente de Cuenta', '2022-05-26', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0046', 'Laura', 'Chavez Rojas', 'laura.chavez46@demo-corp.com', '55-0000-0046', 'Mercadotecnia', 'Disenador Grafico', '2023-10-10', 'active', 'Registro demo MYK-377'),
    ('EMP-0047', 'Carlos', 'Vasquez Castillo', 'carlos.vasquez47@demo-corp.com', '55-0000-0047', 'Soporte', 'Tecnico de Soporte N2', '2024-03-21', 'active', 'Registro demo MYK-377'),
    ('EMP-0048', 'Sofia', 'Mendoza Lopez', 'sofia.mendoza48@demo-corp.com', '55-0000-0048', 'Administracion', 'Recepcionista', '2025-08-05', 'active', 'Registro demo MYK-377'),
    ('EMP-0049', 'Miguel', 'Rojas Rivera', 'miguel.rojas49@demo-corp.com', '55-0000-0049', 'Logistica', 'Chofer', '2018-01-16', 'active', 'Registro demo MYK-377'),
    ('EMP-0050', 'Elena', 'Jimenez Vasquez', 'elena.jimenez50@demo-corp.com', '55-0000-0050', 'Produccion', 'Supervisor de Linea', '2019-06-27', 'active', 'Registro demo MYK-377'),
    ('EMP-0051', 'Jorge', 'Moreno Aguilar', 'jorge.moreno51@demo-corp.com', '55-0000-0051', 'Tecnologia', 'Arquitecto de Software', '2020-11-11', 'active', 'Registro demo MYK-377'),
    ('EMP-0052', 'Patricia', 'Herrera Garcia', 'patricia.herrera52@demo-corp.com', '55-0000-0052', 'Recursos Humanos', 'Reclutador', '2021-04-22', 'active', 'Registro demo MYK-377'),
    ('EMP-0053', 'Ricardo', 'Medina Torres', 'ricardo.medina53@demo-corp.com', '55-0000-0053', 'Finanzas', 'Analista Financiero', '2022-09-06', 'active', 'Registro demo MYK-377'),
    ('EMP-0054', 'Claudia', 'Aguilar Gutierrez', 'claudia.aguilar54@demo-corp.com', '55-0000-0054', 'Operaciones', 'Planificador', '2023-02-17', 'active', 'Registro demo MYK-377'),
    ('EMP-0055', 'Fernando', 'Vargas Herrera', 'fernando.vargas55@demo-corp.com', '55-0000-0055', 'Ventas', 'Vendedor de Campo', '2024-07-01', 'active', 'Registro demo MYK-377'),
    ('EMP-0056', 'Lucia', 'Castillo Solis', 'lucia.castillo56@demo-corp.com', '55-0000-0056', 'Mercadotecnia', 'Content Manager', '2025-12-12', 'active', 'Registro demo MYK-377'),
    ('EMP-0057', 'Alejandro', 'Navarro Sanchez', 'alejandro.navarro57@demo-corp.com', '55-0000-0057', 'Soporte', 'Ingeniero de Soporte', '2018-05-23', 'active', 'Registro demo MYK-377'),
    ('EMP-0058', 'Marta', 'Romero Reyes', 'marta.romero58@demo-corp.com', '55-0000-0058', 'Administracion', 'Especialista en Compras', '2019-10-07', 'active', 'Registro demo MYK-377'),
    ('EMP-0059', 'Francisco', 'Solis Jimenez', 'francisco.solis59@demo-corp.com', '55-0000-0059', 'Logistica', 'Auxiliar de Envios', '2020-03-18', 'active', 'Registro demo MYK-377'),
    ('EMP-0060', 'Carmen', 'Ibarra Navarro', 'carmen.ibarra60@demo-corp.com', '55-0000-0060', 'Produccion', 'Tecnico de Mantenimiento', '2021-08-02', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0061', 'Diego', 'Garcia Gonzalez', 'diego.garcia61@demo-corp.com', '55-0000-0061', 'Tecnologia', 'Desarrollador Backend', '2022-01-13', 'active', 'Registro demo MYK-377'),
    ('EMP-0062', 'Sandra', 'Martinez Gomez', 'sandra.martinez62@demo-corp.com', '55-0000-0062', 'Recursos Humanos', 'Analista de Nomina', '2023-06-24', 'active', 'Registro demo MYK-377'),
    ('EMP-0063', 'Pablo', 'Lopez Mendoza', 'pablo.lopez63@demo-corp.com', '55-0000-0063', 'Finanzas', 'Tesorero', '2024-11-08', 'active', 'Registro demo MYK-377'),
    ('EMP-0064', 'Paula', 'Gonzalez Vargas', 'paula.gonzalez64@demo-corp.com', '55-0000-0064', 'Operaciones', 'Coordinador de Operaciones', '2025-04-19', 'active', 'Registro demo MYK-377'),
    ('EMP-0065', 'Andres', 'Perez Martinez', 'andres.perez65@demo-corp.com', '55-0000-0065', 'Ventas', 'Ejecutivo de Ventas', '2018-09-03', 'active', 'Registro demo MYK-377'),
    ('EMP-0066', 'Silvia', 'Sanchez Flores', 'silvia.sanchez66@demo-corp.com', '55-0000-0066', 'Mercadotecnia', 'Especialista en Marketing', '2019-02-14', 'active', 'Registro demo MYK-377'),
    ('EMP-0067', 'Javier', 'Ramirez Chavez', 'javier.ramirez67@demo-corp.com', '55-0000-0067', 'Soporte', 'Tecnico de Soporte N1', '2020-07-25', 'active', 'Registro demo MYK-377'),
    ('EMP-0068', 'Rocio', 'Torres Medina', 'rocio.torres68@demo-corp.com', '55-0000-0068', 'Administracion', 'Asistente Administrativo', '2021-12-09', 'active', 'Registro demo MYK-377'),
    ('EMP-0069', 'Pedro', 'Flores Ibarra', 'pedro.flores69@demo-corp.com', '55-0000-0069', 'Logistica', 'Coordinador de Almacen', '2022-05-20', 'active', 'Registro demo MYK-377'),
    ('EMP-0070', 'Leticia', 'Rivera Ramirez', 'leticia.rivera70@demo-corp.com', '55-0000-0070', 'Produccion', 'Operador', '2023-10-04', 'active', 'Registro demo MYK-377'),
    ('EMP-0071', 'Raul', 'Gomez Cruz', 'raul.gomez71@demo-corp.com', '55-0000-0071', 'Tecnologia', 'Desarrollador Frontend', '2024-03-15', 'active', 'Registro demo MYK-377'),
    ('EMP-0072', 'Gabriela', 'Diaz Moreno', 'gabriela.diaz72@demo-corp.com', '55-0000-0072', 'Recursos Humanos', 'Coordinador RH', '2025-08-26', 'active', 'Registro demo MYK-377'),
    ('EMP-0073', 'Sergio', 'Reyes Romero', 'sergio.reyes73@demo-corp.com', '55-0000-0073', 'Finanzas', 'Auditor Interno', '2018-01-10', 'active', 'Registro demo MYK-377'),
    ('EMP-0074', 'Adriana', 'Cruz Perez', 'adriana.cruz74@demo-corp.com', '55-0000-0074', 'Operaciones', 'Supervisor de Planta', '2019-06-21', 'active', 'Registro demo MYK-377'),
    ('EMP-0075', 'Oscar', 'Gutierrez Diaz', 'oscar.gutierrez75@demo-corp.com', '55-0000-0075', 'Ventas', 'Gerente de Cuenta', '2020-11-05', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0076', 'Monica', 'Chavez Rojas', 'monica.chavez76@demo-corp.com', '55-0000-0076', 'Mercadotecnia', 'Disenador Grafico', '2021-04-16', 'active', 'Registro demo MYK-377'),
    ('EMP-0077', 'Adrian', 'Vasquez Castillo', 'adrian.vasquez77@demo-corp.com', '55-0000-0077', 'Soporte', 'Tecnico de Soporte N2', '2022-09-27', 'active', 'Registro demo MYK-377'),
    ('EMP-0078', 'Veronica', 'Mendoza Lopez', 'veronica.mendoza78@demo-corp.com', '55-0000-0078', 'Administracion', 'Recepcionista', '2023-02-11', 'active', 'Registro demo MYK-377'),
    ('EMP-0079', 'Hector', 'Rojas Rivera', 'hector.rojas79@demo-corp.com', '55-0000-0079', 'Logistica', 'Chofer', '2024-07-22', 'active', 'Registro demo MYK-377'),
    ('EMP-0080', 'Natalia', 'Jimenez Vasquez', 'natalia.jimenez80@demo-corp.com', '55-0000-0080', 'Produccion', 'Supervisor de Linea', '2025-12-06', 'active', 'Registro demo MYK-377'),
    ('EMP-0081', 'Jose', 'Moreno Aguilar', 'jose.moreno81@demo-corp.com', '55-0000-0081', 'Tecnologia', 'Ingeniero DevOps', '2018-05-17', 'active', 'Registro demo MYK-377'),
    ('EMP-0082', 'Maria', 'Herrera Garcia', 'maria.herrera82@demo-corp.com', '55-0000-0082', 'Recursos Humanos', 'Especialista RH', '2019-10-01', 'active', 'Registro demo MYK-377'),
    ('EMP-0083', 'Juan', 'Medina Torres', 'juan.medina83@demo-corp.com', '55-0000-0083', 'Finanzas', 'Contador', '2020-03-12', 'active', 'Registro demo MYK-377'),
    ('EMP-0084', 'Ana', 'Aguilar Gutierrez', 'ana.aguilar84@demo-corp.com', '55-0000-0084', 'Operaciones', 'Planificador', '2021-08-23', 'active', 'Registro demo MYK-377'),
    ('EMP-0085', 'Luis', 'Vargas Herrera', 'luis.vargas85@demo-corp.com', '55-0000-0085', 'Ventas', 'Vendedor de Campo', '2022-01-07', 'active', 'Registro demo MYK-377'),
    ('EMP-0086', 'Laura', 'Castillo Solis', 'laura.castillo86@demo-corp.com', '55-0000-0086', 'Mercadotecnia', 'Content Manager', '2023-06-18', 'active', 'Registro demo MYK-377'),
    ('EMP-0087', 'Carlos', 'Navarro Sanchez', 'carlos.navarro87@demo-corp.com', '55-0000-0087', 'Soporte', 'Ingeniero de Soporte', '2024-11-02', 'active', 'Registro demo MYK-377'),
    ('EMP-0088', 'Sofia', 'Romero Reyes', 'sofia.romero88@demo-corp.com', '55-0000-0088', 'Administracion', 'Especialista en Compras', '2025-04-13', 'active', 'Registro demo MYK-377'),
    ('EMP-0089', 'Miguel', 'Solis Jimenez', 'miguel.solis89@demo-corp.com', '55-0000-0089', 'Logistica', 'Auxiliar de Envios', '2018-09-24', 'active', 'Registro demo MYK-377'),
    ('EMP-0090', 'Elena', 'Ibarra Navarro', 'elena.ibarra90@demo-corp.com', '55-0000-0090', 'Produccion', 'Tecnico de Mantenimiento', '2019-02-08', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0091', 'Jorge', 'Garcia Gonzalez', 'jorge.garcia91@demo-corp.com', '55-0000-0091', 'Tecnologia', 'Analista de Datos', '2020-07-19', 'active', 'Registro demo MYK-377'),
    ('EMP-0092', 'Patricia', 'Martinez Gomez', 'patricia.martinez92@demo-corp.com', '55-0000-0092', 'Recursos Humanos', 'Reclutador', '2021-12-03', 'active', 'Registro demo MYK-377'),
    ('EMP-0093', 'Ricardo', 'Lopez Mendoza', 'ricardo.lopez93@demo-corp.com', '55-0000-0093', 'Finanzas', 'Analista Financiero', '2022-05-14', 'active', 'Registro demo MYK-377'),
    ('EMP-0094', 'Claudia', 'Gonzalez Vargas', 'claudia.gonzalez94@demo-corp.com', '55-0000-0094', 'Operaciones', 'Coordinador de Operaciones', '2023-10-25', 'active', 'Registro demo MYK-377'),
    ('EMP-0095', 'Fernando', 'Perez Martinez', 'fernando.perez95@demo-corp.com', '55-0000-0095', 'Ventas', 'Ejecutivo de Ventas', '2024-03-09', 'active', 'Registro demo MYK-377'),
    ('EMP-0096', 'Lucia', 'Sanchez Flores', 'lucia.sanchez96@demo-corp.com', '55-0000-0096', 'Mercadotecnia', 'Especialista en Marketing', '2025-08-20', 'active', 'Registro demo MYK-377'),
    ('EMP-0097', 'Alejandro', 'Ramirez Chavez', 'alejandro.ramirez97@demo-corp.com', '55-0000-0097', 'Soporte', 'Tecnico de Soporte N1', '2018-01-04', 'active', 'Registro demo MYK-377'),
    ('EMP-0098', 'Marta', 'Torres Medina', 'marta.torres98@demo-corp.com', '55-0000-0098', 'Administracion', 'Asistente Administrativo', '2019-06-15', 'active', 'Registro demo MYK-377'),
    ('EMP-0099', 'Francisco', 'Flores Ibarra', 'francisco.flores99@demo-corp.com', '55-0000-0099', 'Logistica', 'Coordinador de Almacen', '2020-11-26', 'active', 'Registro demo MYK-377'),
    ('EMP-0100', 'Carmen', 'Rivera Ramirez', 'carmen.rivera100@demo-corp.com', '55-0000-0100', 'Produccion', 'Operador', '2021-04-10', 'active', 'Registro demo MYK-377'),
    ('EMP-0101', 'Diego', 'Gomez Cruz', 'diego.gomez101@demo-corp.com', '55-0000-0101', 'Tecnologia', 'Ingeniero QA', '2022-09-21', 'active', 'Registro demo MYK-377'),
    ('EMP-0102', 'Sandra', 'Diaz Moreno', 'sandra.diaz102@demo-corp.com', '55-0000-0102', 'Recursos Humanos', 'Analista de Nomina', '2023-02-05', 'active', 'Registro demo MYK-377'),
    ('EMP-0103', 'Pablo', 'Reyes Romero', 'pablo.reyes103@demo-corp.com', '55-0000-0103', 'Finanzas', 'Tesorero', '2024-07-16', 'active', 'Registro demo MYK-377'),
    ('EMP-0104', 'Paula', 'Cruz Perez', 'paula.cruz104@demo-corp.com', '55-0000-0104', 'Operaciones', 'Supervisor de Planta', '2025-12-27', 'active', 'Registro demo MYK-377'),
    ('EMP-0105', 'Andres', 'Gutierrez Diaz', 'andres.gutierrez105@demo-corp.com', '55-0000-0105', 'Ventas', 'Gerente de Cuenta', '2018-05-11', 'inactive', 'Registro demo MYK-377'),
    ('EMP-0106', 'Silvia', 'Chavez Rojas', 'silvia.chavez106@demo-corp.com', '55-0000-0106', 'Mercadotecnia', 'Disenador Grafico', '2019-10-22', 'active', 'Registro demo MYK-377'),
    ('EMP-0107', 'Javier', 'Vasquez Castillo', 'javier.vasquez107@demo-corp.com', '55-0000-0107', 'Soporte', 'Tecnico de Soporte N2', '2020-03-06', 'active', 'Registro demo MYK-377'),
    ('EMP-0108', 'Rocio', 'Mendoza Lopez', 'rocio.mendoza108@demo-corp.com', '55-0000-0108', 'Administracion', 'Recepcionista', '2021-08-17', 'active', 'Registro demo MYK-377'),
    ('EMP-0109', 'Pedro', 'Rojas Rivera', 'pedro.rojas109@demo-corp.com', '55-0000-0109', 'Logistica', 'Chofer', '2022-01-01', 'active', 'Registro demo MYK-377'),
    ('EMP-0110', 'Leticia', 'Jimenez Vasquez', 'leticia.jimenez110@demo-corp.com', '55-0000-0110', 'Produccion', 'Supervisor de Linea', '2023-06-12', 'active', 'Registro demo MYK-377'),
    ('EMP-0111', 'Raul', 'Moreno Aguilar', 'raul.moreno111@demo-corp.com', '55-0000-0111', 'Tecnologia', 'Arquitecto de Software', '2024-11-23', 'active', 'Registro demo MYK-377'),
    ('EMP-0112', 'Gabriela', 'Herrera Garcia', 'gabriela.herrera112@demo-corp.com', '55-0000-0112', 'Recursos Humanos', 'Coordinador RH', '2025-04-07', 'active', 'Registro demo MYK-377'),
    ('EMP-0113', 'Sergio', 'Medina Torres', 'sergio.medina113@demo-corp.com', '55-0000-0113', 'Finanzas', 'Auditor Interno', '2018-09-18', 'active', 'Registro demo MYK-377'),
    ('EMP-0114', 'Adriana', 'Aguilar Gutierrez', 'adriana.aguilar114@demo-corp.com', '55-0000-0114', 'Operaciones', 'Planificador', '2019-02-02', 'active', 'Registro demo MYK-377'),
    ('EMP-0115', 'Oscar', 'Vargas Herrera', 'oscar.vargas115@demo-corp.com', '55-0000-0115', 'Ventas', 'Vendedor de Campo', '2020-07-13', 'active', 'Registro demo MYK-377'),
    ('EMP-0116', 'Monica', 'Castillo Solis', 'monica.castillo116@demo-corp.com', '55-0000-0116', 'Mercadotecnia', 'Content Manager', '2021-12-24', 'active', 'Registro demo MYK-377'),
    ('EMP-0117', 'Adrian', 'Navarro Sanchez', 'adrian.navarro117@demo-corp.com', '55-0000-0117', 'Soporte', 'Ingeniero de Soporte', '2022-05-08', 'active', 'Registro demo MYK-377'),
    ('EMP-0118', 'Veronica', 'Romero Reyes', 'veronica.romero118@demo-corp.com', '55-0000-0118', 'Administracion', 'Especialista en Compras', '2023-10-19', 'active', 'Registro demo MYK-377'),
    ('EMP-0119', 'Hector', 'Solis Jimenez', 'hector.solis119@demo-corp.com', '55-0000-0119', 'Logistica', 'Auxiliar de Envios', '2024-03-03', 'active', 'Registro demo MYK-377'),
    ('EMP-0120', 'Natalia', 'Ibarra Navarro', 'natalia.ibarra120@demo-corp.com', '55-0000-0120', 'Produccion', 'Tecnico de Mantenimiento', '2025-08-14', 'inactive', 'Registro demo MYK-377');

-- Dispositivos demo (guard por address)
INSERT INTO devices (name, location, zone, address, port, password, timeout, protocol, status, is_enabled, serial_number, firmware_version)
SELECT 'Reloj Entrada Principal', 'Planta Baja - Lobby', 'Zona A', '192.168.1.201', 4370, 0, 5, 'tcp', 'online', 1, 'DEMO-SN-0001', 'Ver 6.60 Jul 21 2021'
WHERE NOT EXISTS (SELECT 1 FROM devices WHERE address = '192.168.1.201');
INSERT INTO devices (name, location, zone, address, port, password, timeout, protocol, status, is_enabled, serial_number, firmware_version)
SELECT 'Reloj Torre B', 'Piso 3 - Acceso Norte', 'Zona B', '192.168.1.202', 4370, 0, 5, 'tcp', 'online', 1, 'DEMO-SN-0002', 'Ver 6.60 Jul 21 2021'
WHERE NOT EXISTS (SELECT 1 FROM devices WHERE address = '192.168.1.202');
INSERT INTO devices (name, location, zone, address, port, password, timeout, protocol, status, is_enabled, serial_number, firmware_version)
SELECT 'Reloj Almacen', 'Almacen Central', 'Zona C', '192.168.1.203', 4370, 0, 5, 'tcp', 'offline', 1, 'DEMO-SN-0003', NULL
WHERE NOT EXISTS (SELECT 1 FROM devices WHERE address = '192.168.1.203');

-- Usuarios enrolados en los relojes demo (guard por device_id+user_id)
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1001', 'Jose Garcia', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1001');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1002', 'Maria Martinez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1002');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1003', 'Juan Lopez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1003');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1004', 'Ana Gonzalez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1004');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1005', 'Luis Perez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1005');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1006', 'Laura Sanchez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1006');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1007', 'Carlos Ramirez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1007');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1008', 'Sofia Torres', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1008');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1009', 'Miguel Flores', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1009');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1010', 'Elena Rivera', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1010');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1011', 'Jorge Gomez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1011');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1012', 'Patricia Diaz', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1012');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1013', 'Ricardo Reyes', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1013');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1014', 'Claudia Cruz', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1014');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1015', 'Fernando Gutierrez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1015');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1016', 'Lucia Chavez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1016');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1017', 'Alejandro Vasquez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1017');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1018', 'Marta Mendoza', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1018');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1019', 'Francisco Rojas', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1019');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1020', 'Carmen Jimenez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1020');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1021', 'Diego Moreno', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1021');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1022', 'Sandra Herrera', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1022');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1023', 'Pablo Medina', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1023');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1024', 'Paula Aguilar', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1024');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1025', 'Andres Vargas', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1025');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1026', 'Silvia Castillo', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1026');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1027', 'Javier Navarro', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1027');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1028', 'Rocio Romero', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1028');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1029', 'Pedro Solis', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1029');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1030', 'Leticia Ibarra', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.201'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1030');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1001', 'Raul Garcia', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1001');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1002', 'Gabriela Martinez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1002');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1003', 'Sergio Lopez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1003');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1004', 'Adriana Gonzalez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1004');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1005', 'Oscar Perez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1005');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1006', 'Monica Sanchez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1006');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1007', 'Adrian Ramirez', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1007');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1008', 'Veronica Torres', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1008');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1009', 'Hector Flores', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1009');
INSERT INTO device_users (device_id, user_id, name, privilege, group_id, user_role)
SELECT d.id, '1010', 'Natalia Rivera', 0, '1', 0 FROM devices d
WHERE d.address = '192.168.1.202'
  AND NOT EXISTS (SELECT 1 FROM device_users du
                  WHERE du.device_id = d.id AND du.user_id = '1010');

-- Vinculos colaborador <-> usuario de reloj (INSERT OR IGNORE por PK)
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1001' FROM employees WHERE employee_code = 'EMP-0001';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1002' FROM employees WHERE employee_code = 'EMP-0002';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1003' FROM employees WHERE employee_code = 'EMP-0003';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1004' FROM employees WHERE employee_code = 'EMP-0004';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1005' FROM employees WHERE employee_code = 'EMP-0005';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1006' FROM employees WHERE employee_code = 'EMP-0006';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1007' FROM employees WHERE employee_code = 'EMP-0007';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1008' FROM employees WHERE employee_code = 'EMP-0008';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1009' FROM employees WHERE employee_code = 'EMP-0009';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1010' FROM employees WHERE employee_code = 'EMP-0010';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1011' FROM employees WHERE employee_code = 'EMP-0011';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1012' FROM employees WHERE employee_code = 'EMP-0012';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1013' FROM employees WHERE employee_code = 'EMP-0013';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1014' FROM employees WHERE employee_code = 'EMP-0014';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1015' FROM employees WHERE employee_code = 'EMP-0015';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1016' FROM employees WHERE employee_code = 'EMP-0016';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1017' FROM employees WHERE employee_code = 'EMP-0017';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1018' FROM employees WHERE employee_code = 'EMP-0018';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1019' FROM employees WHERE employee_code = 'EMP-0019';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1020' FROM employees WHERE employee_code = 'EMP-0020';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1021' FROM employees WHERE employee_code = 'EMP-0021';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1022' FROM employees WHERE employee_code = 'EMP-0022';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1023' FROM employees WHERE employee_code = 'EMP-0023';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1024' FROM employees WHERE employee_code = 'EMP-0024';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1025' FROM employees WHERE employee_code = 'EMP-0025';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1026' FROM employees WHERE employee_code = 'EMP-0026';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1027' FROM employees WHERE employee_code = 'EMP-0027';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1028' FROM employees WHERE employee_code = 'EMP-0028';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1029' FROM employees WHERE employee_code = 'EMP-0029';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0001', '1030' FROM employees WHERE employee_code = 'EMP-0030';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1001' FROM employees WHERE employee_code = 'EMP-0031';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1002' FROM employees WHERE employee_code = 'EMP-0032';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1003' FROM employees WHERE employee_code = 'EMP-0033';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1004' FROM employees WHERE employee_code = 'EMP-0034';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1005' FROM employees WHERE employee_code = 'EMP-0035';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1006' FROM employees WHERE employee_code = 'EMP-0036';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1007' FROM employees WHERE employee_code = 'EMP-0037';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1008' FROM employees WHERE employee_code = 'EMP-0038';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1009' FROM employees WHERE employee_code = 'EMP-0039';
INSERT OR IGNORE INTO employee_device_links (employee_id, device_serial, device_user_id)
SELECT id, 'DEMO-SN-0002', '1010' FROM employees WHERE employee_code = 'EMP-0040';

-- Usuarios WebGUI demo (contrasena: demo1234, Argon2id precomputado)
-- INSERT OR IGNORE: no toca cuentas existentes (p.ej. el admin del setup).
INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_active)
VALUES
    ('demo.admin', 'demo.admin@demo-corp.com', '$argon2id$v=19$m=65536,t=3,p=4$6mGCUIrdQW7Txcq5ttrsMA$m9rBgLbS7AWPKVAdDowHoMqzYjdMy8sj/QbqsmvuEHw', 'Admin Demo', 'admin', 1),
    ('demo.rrhh', 'demo.rrhh@demo-corp.com', '$argon2id$v=19$m=65536,t=3,p=4$6mGCUIrdQW7Txcq5ttrsMA$m9rBgLbS7AWPKVAdDowHoMqzYjdMy8sj/QbqsmvuEHw', 'Rosa Hernandez', 'user', 1),
    ('demo.finanzas', 'demo.finanzas@demo-corp.com', '$argon2id$v=19$m=65536,t=3,p=4$6mGCUIrdQW7Txcq5ttrsMA$m9rBgLbS7AWPKVAdDowHoMqzYjdMy8sj/QbqsmvuEHw', 'Felipe Navarro', 'user', 1),
    ('demo.soporte', 'demo.soporte@demo-corp.com', '$argon2id$v=19$m=65536,t=3,p=4$6mGCUIrdQW7Txcq5ttrsMA$m9rBgLbS7AWPKVAdDowHoMqzYjdMy8sj/QbqsmvuEHw', 'Susana Ortega', 'user', 1),
    ('demo.ventas', 'demo.ventas@demo-corp.com', '$argon2id$v=19$m=65536,t=3,p=4$6mGCUIrdQW7Txcq5ttrsMA$m9rBgLbS7AWPKVAdDowHoMqzYjdMy8sj/QbqsmvuEHw', 'Victor Salgado', 'user', 1);

