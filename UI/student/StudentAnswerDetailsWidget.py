from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
from model.answer_model import Answer
from model.question_model import Question


class AnswerDetailsWidget(QWidget):

    def __init__(self, authorized_user):
        super().__init__()

        self.authorized_user = authorized_user

        self.__initUi()
        self.hide()

    def __initUi(self):
        teacher_question_container = QWidget(self)
        teacher_question_container.setObjectName("teacher_container")  # Setta un ID per il container
        teacher_question_container.setStyleSheet('''
            #teacher_container {
                background-color: rgba(52, 143, 235, 0.1);
                border-radius: 20px;
            }''')

        self.teacher_answer_layout = QVBoxLayout(teacher_question_container)

        self.question_label = QLabel("-")
        self.question_label.setStyleSheet('''
                    QLabel {
                        font-size: 14px; 
                        font-weight: bold;
                    }
                ''')
        self.question_label.setWordWrap(True)

        self.answer_label = QLabel("-")
        self.answer_label.setWordWrap(True)

        self.result_label = QLabel("-")

        lbl = QLabel("DOMANDA")
        lbl.setStyleSheet('''
                            QLabel {
                                font-size: 12px; 
                                font-weight: 300;
                            }
                        ''')
        self.teacher_answer_layout.addWidget(lbl)
        self.teacher_answer_layout.addWidget(self.question_label)

        self.student_answer_layout = QVBoxLayout()
        self.student_answer_layout.insertSpacing(10, 20)

        lbl = QLabel("RISPOSTA")
        lbl.setStyleSheet('''
                                QLabel {
                                    font-size: 12px; 
                                    font-weight: 300;
                                }
                            ''')
        self.student_answer_layout.addWidget(lbl)
        self.student_answer_layout.addWidget(self.answer_label)

        lbl = QLabel("RISULTATO")
        lbl.setStyleSheet('''
                                    QLabel {
                                        font-size: 12px; 
                                        font-weight: 300;
                                    }
                                ''')
        self.student_answer_layout.addWidget(lbl)
        self.student_answer_layout.addWidget(self.result_label)

        scroll_vertical_layout = QVBoxLayout()
        scroll = QScrollArea()  # Scroll Area which contains the widgets, set as the centralWidget
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_widget = QWidget()

        scroll_widget.setLayout(scroll_vertical_layout)
        scroll.setWidget(scroll_widget)
        # Scroll Area Properties
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)

        scroll_vertical_layout.addWidget(teacher_question_container)
        scroll_vertical_layout.addLayout(self.student_answer_layout)
        scroll_vertical_layout.addStretch()

        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)

        self.setLayout(lay)

    def replaceAnswer(self, question: Question, answer: Answer):
        self.question_label.setText(question.domanda)
        self.answer_label.setText(answer.risposta)
        self.result_label.setText("In attesa di valutazione" if answer.voto_docente == -1 else str(answer.voto_docente))

        if answer.voto_docente > -1 and answer.voto_docente >= 3:
            self.result_label.setStyleSheet('''
                                QLabel {
                                    font-size: 12px; 
                                    font-weight: bold;
                                    color: #32a852;
                                }
                            ''')
        else:
            self.result_label.setStyleSheet('''
                                QLabel {
                                    font-size: 12px; 
                                    font-weight: bold;
                                    color: #a83232;
                                }
                            ''')

        if self.isHidden():
            self.show()
