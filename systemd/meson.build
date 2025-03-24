conf_data = configuration_data()
conf_data.set('bin_dir', get_option('prefix') / get_option('bindir'))

configure_file(input : 'showcontrol.service.in',
                output : 'showcontrol.service',
                configuration: conf_data,
                install_dir: '/etc/systemd/user'
)
